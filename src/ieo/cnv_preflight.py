"""
Preflight de ``.cnv`` bajo ``data/cnv/``: lotes con nomenclatura no estándar, dudas y puerta.

Objetivo: escalar a carpetas nuevas (p. ej. ``St.1 CNVs``) sin asumir ``AAAA/``,
listar ficheros dudosos y formular preguntas para el operador antes o después de correr
``run/main.py``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from ieo.cnv_layout import first_segment_under_cnv_root, is_non_year_shard_under_cnv
from ieo.paths import cnv_dir, cnv_file_label_under_root
from ieo.ingest_gate import evaluate_file
from ieo.io.cnv_header import (
    parse_cnv_start_time_iso_from_path,
    parse_cnv_station_number_from_path,
)
from ieo.io.cnv_radial import classify_cnv_radial_detailed


ScanMode = Literal["non_year_shards", "all"]


def _iter_cnv_paths(project_root: Path) -> list[Path]:
    root = cnv_dir(project_root)
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.cnv"))


def _filter_paths(
    cnv_root: Path,
    paths: list[Path],
    *,
    mode: ScanMode,
) -> list[Path]:
    if mode == "all":
        return list(paths)
    return [p for p in paths if is_non_year_shard_under_cnv(cnv_root, p)]


def _build_questions(by_folder: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    for folder, block in sorted(by_folder.items()):
        radials: dict[str, int] = block.get("radial_id_counts") or {}
        if len(radials) > 1:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(radials.items(), key=lambda x: -x[1]))
            questions.append(
                f"La carpeta «{folder}» mezcla varias radiales detectadas ({parts}). "
                "¿Es correcto que convivan en el mismo lote o convendría separarlas por radial?"
            )
        n_des = int(radials.get("desconocida", 0))
        if n_des > 0:
            questions.append(
                f"En «{folder}» hay {n_des} fichero(s) con radial «desconocida». "
                "¿Puede revisar ** Cruise:** / coordenadas o el nombre de fichero para mejorar la clasificación?"
            )
        n_conf = int(block.get("n_conflict_cruise_vs_geo") or 0)
        if n_conf > 0:
            questions.append(
                f"En «{folder}» hay {n_conf} caso(s) con conflicto crucero vs. posición geográfica. "
                "¿Cuál criterio debe prevalecer en esos casts?"
            )
        n_rej = int(block.get("n_gate_reject") or 0)
        n_tot = int(block.get("n_files") or 0)
        if n_tot and n_rej == n_tot:
            questions.append(
                f"Todos los ficheros de «{folder}» fallan el control previo (puerta). "
                "Revise el primer motivo en la lista de «dubios» o en motivos de cuarentena agregados."
            )
        elif n_rej > max(3, n_tot // 5):
            questions.append(
                f"En «{folder}» el control previo rechaza {n_rej} de {n_tot} ficheros. "
                "¿Los formatos de cabecera SBE son homogéneos en ese lote?"
            )
    if not questions:
        questions.append(
            "No se detectaron incoherencias graves entre carpetas nuevas y clasificación/puerta. "
            "Si algo falla en campañas concretas, ejecute de nuevo el preflight tras añadir datos."
        )
    return questions


def run_cnv_preflight(
    project_root: Path,
    *,
    mode: ScanMode = "non_year_shards",
    max_dubious: int = 400,
    include_per_file_rows: bool = True,
) -> dict[str, Any]:
    """
    Analiza ``.cnv`` (por defecto solo bajo carpetas cuyo nombre no es ``YYYY``).

    Devuelve un dict JSON-serializable con agregados, preguntas sugeridas y muestra de dubios.
    """
    cnv_root = cnv_dir(project_root)
    all_paths = _iter_cnv_paths(project_root)
    paths = _filter_paths(cnv_root, all_paths, mode=mode)

    by_folder: dict[str, dict[str, Any]] = {}
    dubious: list[dict[str, Any]] = []
    gate_reasons_global: Counter[str] = Counter()
    rows_compact: list[dict[str, Any]] = []

    for p in paths:
        folder = first_segment_under_cnv_root(cnv_root, p) or "."
        if folder not in by_folder:
            by_folder[folder] = {
                "n_files": 0,
                "radial_id_counts": Counter(),
                "n_gate_ok": 0,
                "n_gate_reject": 0,
                "gate_reason_counts": Counter(),
                "n_conflict_cruise_vs_geo": 0,
                "n_sin_start_time": 0,
            }
        blk = by_folder[folder]
        blk["n_files"] += 1

        det = classify_cnv_radial_detailed(p)
        rid = det.radial_id or "desconocida"
        blk["radial_id_counts"][rid] += 1
        if det.conflict_cruise_vs_geo:
            blk["n_conflict_cruise_vs_geo"] += 1

        gate = evaluate_file(p, project_root=project_root)
        if gate.accepted:
            blk["n_gate_ok"] += 1
        else:
            blk["n_gate_reject"] += 1
            for r in gate.reasons:
                blk["gate_reason_counts"][r] += 1
                gate_reasons_global[r] += 1

        st_iso = parse_cnv_start_time_iso_from_path(p)
        if st_iso is None:
            blk["n_sin_start_time"] += 1

        stn = parse_cnv_station_number_from_path(p)
        label = cnv_file_label_under_root(cnv_root, p)

        issues: list[str] = []
        if not gate.accepted:
            issues.extend(gate.reasons)
        if rid == "desconocida":
            issues.append("radial_id=desconocida")
        if det.conflict_cruise_vs_geo:
            issues.append("conflicto Cruise vs. geo")

        if len(dubious) < max_dubious and issues:
            dubious.append(
                {
                    "path": p.as_posix(),
                    "file_label": label,
                    "folder_shard": folder,
                    "issues": issues,
                    "radial_id": rid,
                    "rule": det.rule,
                }
            )

        if include_per_file_rows:
            rows_compact.append(
                {
                    "path_posix": p.as_posix(),
                    "file_label": label,
                    "folder_shard": folder,
                    "radial_id": det.radial_id,
                    "rule": det.rule,
                    "campana_rcan": det.campana_rcan,
                    "conflict_cruise_vs_geo": det.conflict_cruise_vs_geo,
                    "gate_ok": gate.accepted,
                    "gate_reasons": list(gate.reasons),
                    "start_time_iso": st_iso,
                    "station": stn,
                }
            )

    # Serializar contadores
    for folder, blk in by_folder.items():
        blk["radial_id_counts"] = dict(sorted(blk["radial_id_counts"].items(), key=lambda x: (-x[1], x[0])))
        blk["gate_reason_counts"] = dict(
            sorted(blk["gate_reason_counts"].items(), key=lambda x: (-x[1], str(x[0])))[:12]
        )

    questions = _build_questions(by_folder)

    out: dict[str, Any] = {
        "scan_mode": mode,
        "cnv_root": str(cnv_root),
        "n_cnv_total_repo": len(all_paths),
        "n_scanned": len(paths),
        "by_folder": by_folder,
        "questions": questions,
        "dubious_sample": dubious[:max_dubious],
        "n_dubious_capped": len(dubious),
        "gate_reasons_global": dict(sorted(gate_reasons_global.items(), key=lambda x: (-x[1], str(x[0])))),
    }
    if include_per_file_rows:
        out["rows"] = rows_compact
    return out


def write_preflight_json(report: dict[str, Any], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def print_preflight_dialogue(report: dict[str, Any], *, file=None) -> None:
    """Imprime resumen legible + bloque de diálogo (preguntas)."""
    import sys

    f = file or sys.stdout
    print("=== Preflight data/cnv ===", file=f)
    print(f"Modo escaneo     : {report.get('scan_mode')}", file=f)
    print(f".cnv en repo     : {report.get('n_cnv_total_repo')}", file=f)
    print(f"Ficheros analizados: {report.get('n_scanned')}", file=f)
    by_folder = report.get("by_folder") or {}
    if by_folder:
        print("\nPor carpeta (lote):", file=f)
        for folder, blk in sorted(by_folder.items()):
            print(f"  · {folder}: {blk.get('n_files')} ficheros", file=f)
            print(f"      radial_id: {blk.get('radial_id_counts')}", file=f)
            print(
                f"      puerta OK / rechazados: {blk.get('n_gate_ok')} / {blk.get('n_gate_reject')}",
                file=f,
            )
            if blk.get("n_conflict_cruise_vs_geo"):
                print(f"      conflictos cruise/geo: {blk['n_conflict_cruise_vs_geo']}", file=f)
            if blk.get("n_sin_start_time"):
                print(f"      sin # start_time: {blk['n_sin_start_time']}", file=f)
    print("\n--- Preguntas sugeridas (revisión humana) ---", file=f)
    for i, q in enumerate(report.get("questions") or [], start=1):
        print(f"  {i}. {q}", file=f)
    dub = report.get("dubious_sample") or []
    if dub:
        print(f"\n--- Ficheros dudosos (máx. {len(dub)} listados) ---", file=f)
        for item in dub[:40]:
            print(f"  · {item.get('file_label')}", file=f)
            for iss in item.get("issues") or []:
                short = iss if len(iss) <= 140 else iss[:137] + "…"
                print(f"      - {short}", file=f)
        if len(dub) > 40:
            print(f"  … y {len(dub) - 40} más en el JSON completo.", file=f)
    print("\nMotivos globales de puerta (rechazos):", file=f)
    for reason, n in list((report.get("gate_reasons_global") or {}).items())[:8]:
        short = reason if len(reason) <= 120 else reason[:117] + "…"
        print(f"  [{n}] {short}", file=f)

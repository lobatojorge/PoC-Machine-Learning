#!/usr/bin/env python3
"""
Auditoría de la última corrida del pipeline IEO-Orchestrator (solo lectura).

Lee la corrida más reciente en ``outputs/runs/`` (por ``generated_at_utc`` en
``run_summary.json``) y sus Parquet ``*_ctd_clean`` / ``*_ctd_anomalies``. Genera:

  - ``outputs/audit_report.md``
  - ``outputs/audit_report_gijon_bars.png``

Uso (desde la raíz del repo)::

    python scripts/audit_report.py

Idempotente: no modifica datos de entrada ni corridas; solo escribe los informes.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "outputs" / "runs"
OUT_MD = ROOT / "outputs" / "audit_report.md"
OUT_PNG = ROOT / "outputs" / "audit_report_gijon_bars.png"

GIJON_RADIAL = "gijon"
TOP_STATIONS = 8


@dataclass
class RunRecord:
    run_id: str
    path: Path
    summary: dict[str, Any]
    duration_s: float | None = None
    n_clean_rows: int = 0
    n_anomaly_rows: int = 0


def _parse_utc(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _run_duration_seconds(run_root: Path, summary: dict[str, Any]) -> float | None:
    end = _parse_utc(summary.get("generated_at_utc"))
    prov_path = run_root / "provenance.json"
    start: datetime | None = None
    if prov_path.is_file():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            start = _parse_utc(prov.get("created_at_utc"))
        except (OSError, json.JSONDecodeError):
            start = None
    if start and end and end >= start:
        return (end - start).total_seconds()
    return None


def _parquet_row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        import polars as pl

        return int(pl.scan_parquet(path).select(pl.len()).collect().item())
    except ImportError:
        pass
    try:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    except ImportError:
        pass
    import pandas as pd

    return len(pd.read_parquet(path))


def _iter_clean_anomaly_parquets(data_dir: Path) -> tuple[list[Path], list[Path]]:
    if not data_dir.is_dir():
        return [], []
    consolidated_clean = data_dir / "perfiles_all.ctd_clean.parquet"
    consolidated_anom = data_dir / "perfiles_all.ctd_anomalies.parquet"
    if consolidated_clean.is_file():
        clean = [consolidated_clean]
    else:
        clean = sorted(data_dir.glob("*.ctd_clean.parquet"))
    if consolidated_anom.is_file():
        anom = [consolidated_anom]
    else:
        anom = sorted(data_dir.glob("*.ctd_anomalies.parquet"))
    return clean, anom


def _count_parquet_rows(paths: list[Path]) -> int:
    return sum(_parquet_row_count(p) for p in paths)


def _load_run_record(run_dir: Path, *, count_parquet_rows: bool) -> RunRecord | None:
    summary_path = run_dir / "run_summary.json"
    if not summary_path.is_file():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rec = RunRecord(
        run_id=run_dir.name,
        path=run_dir,
        summary=summary,
        duration_s=_run_duration_seconds(run_dir, summary),
    )
    if count_parquet_rows:
        data_dir = run_dir / "data"
        clean_paths, anom_paths = _iter_clean_anomaly_parquets(data_dir)
        rec.n_clean_rows = _count_parquet_rows(clean_paths)
        rec.n_anomaly_rows = _count_parquet_rows(anom_paths)
    return rec


def _discover_run_dirs() -> list[tuple[Path, str]]:
    """(run_dir, generated_at_utc) para ordenar sin leer Parquet."""
    if not RUNS_DIR.is_dir():
        return []
    found: list[tuple[Path, str]] = []
    for run_dir in RUNS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "run_summary.json"
        if not summary_path.is_file():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = str(summary.get("generated_at_utc") or "")
        found.append((run_dir, ts))
    found.sort(key=lambda x: x[1], reverse=True)
    return found


def _load_latest_run() -> tuple[RunRecord | None, int]:
    """Última corrida con conteo de filas Parquet; ``n`` = corridas con resumen."""
    discovered = _discover_run_dirs()
    if not discovered:
        return None, 0
    latest = _load_run_record(discovered[0][0], count_parquet_rows=True)
    return latest, len(discovered)


def _ingest_int(summary: dict[str, Any], key: str) -> int:
    ingest = summary.get("ingest") or {}
    try:
        return int(ingest.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _ingest_dict(summary: dict[str, Any]) -> dict[str, Any]:
    raw = summary.get("ingest")
    return raw if isinstance(raw, dict) else {}


def _read_checkpoint_metrics(run_root: Path, step_id: str) -> dict[str, Any]:
    path = run_root / "checkpoints" / f"{step_id}.metrics.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    metrics = payload.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _metric_int(metrics: dict[str, Any], key: str) -> int | None:
    if key not in metrics:
        return None
    try:
        return int(metrics[key])
    except (TypeError, ValueError):
        return None


def _count_per_profile_parquets(data_dir: Path, suffix: str) -> int:
    """Cuenta `*.{suffix}` excluyendo consolidados ``perfiles_all.*``."""
    if not data_dir.is_dir():
        return 0
    return sum(
        1
        for p in data_dir.glob(f"*.{suffix}")
        if p.is_file() and not p.name.startswith("perfiles_all.")
    )


@dataclass(frozen=True)
class FunnelRow:
    step: str
    remain: int | None
    removed: int | None
    note: str


def _build_file_funnel(latest: RunRecord) -> list[FunnelRow]:
    """
    Embudo de ficheros/perfiles a partir de ``run_summary`` y checkpoints de la corrida.
    """
    summary = latest.summary
    ingest = _ingest_dict(summary)
    run_root = latest.path
    data_dir = run_root / "data"

    filtro = str(ingest.get("filtro_radial") or "todas")
    inventario = _ingest_int(summary, "inventario_total") or _ingest_int(summary, "n_cnv_encontrados")
    omitidas_radial = _ingest_int(summary, "n_omitidas_otra_radial")
    candidatos = _ingest_int(summary, "n_cudillero_candidatos")
    gate_ok = _ingest_int(summary, "n_puerta_ok")
    cuarentena = _ingest_int(summary, "n_cuarentena")
    canonical = _ingest_int(summary, "n_parquet_canonicos")
    err_ingesta = _ingest_int(summary, "n_error_tras_puerta")
    qc_cache = _ingest_int(summary, "n_qc_desde_cache")
    canon_reuse = _ingest_int(summary, "n_canonical_reutilizados")
    canon_new = _ingest_int(summary, "n_canonical_nuevos")

    ing_m = _read_checkpoint_metrics(run_root, "01_ingestion")
    contract_m = _read_checkpoint_metrics(run_root, "01b_radial_contract")
    anom_m = _read_checkpoint_metrics(run_root, "02_anomalies")

    n_canonical_disk = _count_per_profile_parquets(data_dir, "ctd_canonical.parquet")
    n_clean_disk = _count_per_profile_parquets(data_dir, "ctd_clean.parquet")

    if canonical <= 0 and n_canonical_disk > 0:
        canonical = n_canonical_disk

    n_contract_files = _metric_int(contract_m, "n_files_with_errors")
    if n_contract_files is None and canonical > 0:
        n_contract_files = 0

    n_qc_fail = _metric_int(anom_m, "n_step_errors")
    if n_qc_fail is None:
        err_payload = _read_checkpoint_metrics(run_root, "02_anomalies_errors")
        n_qc_fail = _metric_int(err_payload, "n_errors")
    n_qc_fail = n_qc_fail or 0

    n_qc_inputs = _metric_int(anom_m, "n_inputs")
    if n_qc_inputs is not None:
        n_clean = max(0, n_qc_inputs - n_qc_fail)
    elif canonical > 0:
        n_clean = max(0, canonical - n_qc_fail)
    else:
        n_clean = n_clean_disk

    rows: list[FunnelRow] = []

    if inventario > 0 and inventario != candidatos and omitidas_radial == 0:
        rows.append(
            FunnelRow(
                "Inventario `.cnv` en disco",
                inventario,
                None,
                "Todos los ficheros bajo `data/cnv/` (referencia).",
            )
        )

    if omitidas_radial > 0:
        en_alcance = candidatos if candidatos > 0 else max(0, inventario - omitidas_radial)
        rows.append(
            FunnelRow(
                f"00 · Alcance radial (`{filtro}`)",
                en_alcance,
                omitidas_radial,
                "No entran al control previo (otra radial / sin clasificar).",
            )
        )
    elif candidatos > 0:
        rows.append(
            FunnelRow(
                "00 · Alcance del pipeline",
                candidatos,
                None,
                f"Alcance: **{filtro}** (misma cadena para todas las radiales en disco).",
            )
        )

    evaluados = candidatos if candidatos > 0 else gate_ok + cuarentena
    rows.append(
        FunnelRow(
            "00 · Control previo (puerta)",
            gate_ok,
            cuarentena,
            "Rechazados → `data/quarantine/` (cabecera, columnas mínimas, etc.).",
        )
    )

    ingest_detail_json = str(ingest.get("ingestion_failed_detail_json") or "")
    ingesta_note = (
        "Fallo al leer/normalizar tras pasar la puerta (sin `.ctd_canonical.parquet`); "
        "el original sigue en `data/cnv/` (no se copia a cuarentena)."
    )
    if ingest_detail_json:
        ingesta_note += f" Listado: `checkpoints/{ingest_detail_json}`."
    if canon_reuse or canon_new:
        ingesta_note += f" Reutilizados: {canon_reuse}, nuevos: {canon_new}."
    rows.append(
        FunnelRow(
            "01 · Ingesta → Parquet canónico",
            canonical,
            err_ingesta,
            ingesta_note,
        )
    )

    if canonical > 0:
        sin_err_contrato = canonical - (n_contract_files or 0)
        rows.append(
            FunnelRow(
                "01b · Contrato radial (evaluación)",
                canonical,
                None,
                f"Se evalúan **todos** los canónicos. "
                f"**{n_contract_files or 0}** con ≥1 regla ERROR; "
                f"**{sin_err_contrato}** sin ERROR de fichero. "
                "El contrato no elimina perfiles: siguen al IF.",
            )
        )

        qc_note = (
            "Salida: `*_ctd_clean.parquet` y `*_ctd_anomalies.parquet` por perfil."
            + (f" QC restaurado desde caché: {qc_cache}." if qc_cache else "")
        )
        if n_clean_disk > 0 and n_clean_disk != n_clean:
            qc_note += (
                f" En disco hay **{n_clean_disk:,}** ficheros `*_ctd_clean` distintos por `stem` "
                f"(menor que {n_clean:,} si varios `.cnv` comparten nombre de fichero)."
            )
        rows.append(
            FunnelRow(
                "02 · Contrato + Isolation Forest (QC)",
                n_clean,
                n_qc_fail,
                qc_note,
            )
        )

        contract_err_rows = int(summary.get("contract_errors") or 0)
        n_anom_rows = int(summary.get("n_anomalies") or 0)
        if contract_err_rows or n_anom_rows:
            rows.append(
                FunnelRow(
                    "— (detalle filas, no ficheros)",
                    None,
                    None,
                    f"Reglas de contrato incumplidas (filas): **{contract_err_rows:,}**. "
                    f"Filas marcadas anómalas por IF: **{n_anom_rows:,}**.",
                )
            )

    return rows


def _format_funnel_markdown(rows: list[FunnelRow]) -> list[str]:
    if not rows:
        return ["_Sin datos de embudo para esta corrida._", ""]
    lines = [
        "## Embudo de ficheros por paso",
        "",
        "Cuenta **ficheros fuente / perfiles** (un `.cnv` aceptado → un Parquet canónico → "
        "un trío clean/anomalies/audit). Los pasos 01b y 02 no reducen el número de ficheros "
        "salvo fallo de ingesta o de QC; el contrato solo **marca** incumplimientos.",
        "",
        "| Paso | Tras el paso | Retirados aquí | Qué ocurre con los retirados |",
        "|------|-------------:|---------------:|------------------------------|",
    ]
    for row in rows:
        remain = "—" if row.remain is None else f"{row.remain:,}"
        removed = "—" if row.removed is None else (f"{row.removed:,}" if row.removed else "0")
        note = row.note.replace("|", "\\|")
        lines.append(f"| {row.step} | {remain} | {removed} | {note} |")
    lines.append("")
    return lines


def _normalize_quarantine_reason(reason: str) -> str:
    """Agrupa motivos largos en etiquetas cortas para el resumen."""
    r = reason.strip()
    if not r:
        return "(vacío)"
    if r.startswith("[aviso]"):
        return "Error al copiar a cuarentena"
    if "no existe" in r.lower():
        return "Fichero inexistente"
    if "extensión" in r.lower() or "extension" in r.lower():
        return "Extensión no .cnv"
    if "vacío" in r.lower() or "0 bytes" in r.lower():
        return "Fichero vacío"
    if "columnas" in r.lower() and "cabecera" in r.lower():
        return "Cabecera SeaBird no parseable"
    if "temperatura" in r.lower():
        return "Sin columna de temperatura en cabecera"
    if "presión" in r.lower() or "profundidad" in r.lower():
        return "Sin columna de presión/profundidad"
    if "tiempo" in r.lower() or "start_time" in r.lower():
        return "Sin referencia temporal"
    if len(r) > 100:
        return r[:97] + "..."
    return r


def _load_ingestion_failures(run_root: Path, ingest: dict[str, Any]) -> list[dict[str, Any]]:
    """Listado completo de fallos de ingesta (checkpoints o muestra en run_summary)."""
    detail_name = ingest.get("ingestion_failed_detail_json") or "01_ingestion_failed_detail.json"
    detail_path = run_root / "checkpoints" / str(detail_name)
    if detail_path.is_file():
        try:
            payload = json.loads(detail_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [x for x in payload if isinstance(x, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    muestra = ingest.get("muestra_error_ingesta")
    if isinstance(muestra, list):
        return [x for x in muestra if isinstance(x, dict)]
    # Corridas anteriores al listado dedicado: hasta 40 mensajes en metrics del paso 01
    metrics_path = run_root / "checkpoints" / "01_ingestion.metrics.json"
    if metrics_path.is_file():
        try:
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            errors = payload.get("errors")
            if isinstance(errors, list):
                out: list[dict[str, Any]] = []
                for raw in errors:
                    if not isinstance(raw, str) or ": " not in raw:
                        continue
                    name, rest = raw.split(": ", 1)
                    et, _, reason = rest.partition(": ")
                    out.append(
                        {
                            "file": name,
                            "file_label": name,
                            "path": "",
                            "error_type": et or "Error",
                            "reason": reason or rest,
                            "reason_short": reason or rest,
                        }
                    )
                return out
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _normalize_ingest_failure_reason(reason: str) -> str:
    """Agrupa motivos largos (misma lógica que ``_short_ingest_error_label`` en cli)."""
    r = reason.strip()
    if "Faltan columnas requeridas" in r and "estacion" in r:
        return "Falta columna estación tras normalización"
    if "No se encontraron datos tras la cabecera" in r:
        return "Sin datos tras cabecera (*END*)"
    if "no contiene filas de datos válidas" in r:
        return "Sin filas de datos numéricas válidas"
    if "ninguna fila" in r.lower() and "radial" in r.lower():
        return "Filtro radial dejó 0 filas"
    if len(r) > 100:
        return r[:97] + "..."
    return r


def _ingest_failure_reasons(ingest: dict[str, Any], failures: list[dict[str, Any]]) -> Counter[str]:
    motivos = ingest.get("motivos_error_ingesta")
    if isinstance(motivos, dict) and motivos:
        counter: Counter[str] = Counter()
        for reason, count in motivos.items():
            counter[str(reason)] += int(count or 0)
        return counter
    counter: Counter[str] = Counter()
    for item in failures:
        raw = str(item.get("reason_short") or item.get("reason") or "(sin motivo)")
        counter[_normalize_ingest_failure_reason(raw)] += 1
    return counter


def _collect_quarantine_reasons(rec: RunRecord | None) -> Counter[str]:
    """Motivos de cuarentena registrados en el ``run_summary`` de una corrida."""
    counter: Counter[str] = Counter()
    if rec is None:
        return counter
    ingest = rec.summary.get("ingest") or {}
    motivos = ingest.get("motivos_cuarentena") or {}
    if isinstance(motivos, dict):
        for reason, count in motivos.items():
            counter[_normalize_quarantine_reason(str(reason))] += int(count or 0)
    return counter


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes} min {sec} s"
    hours, rem = divmod(minutes, 60)
    return f"{hours} h {rem} min"


def _gijon_station_counts(run_root: Path) -> dict[str, tuple[int, int]]:
    """
    Filas limpias vs anómalas por estación (Gijón) en una corrida.
    Devuelve {etiqueta_estacion: (n_clean, n_anomaly)}.
    """
    data_dir = run_root / "data"
    clean_paths, anom_paths = _iter_clean_anomaly_parquets(data_dir)
    if not clean_paths and not anom_paths:
        return {}

    try:
        import polars as pl
    except ImportError:
        return _gijon_station_counts_pandas(run_root)

    def _counts_by_station(paths: list[Path]) -> Counter[str]:
        out: Counter[str] = Counter()
        for p in paths:
            schema_names = pl.scan_parquet(p).collect_schema().names()
            cols_lower = {c.lower(): c for c in schema_names}
            rid_col = cols_lower.get("radial_id")
            est_col = cols_lower.get("estacion")
            if not est_col:
                continue
            lf = pl.scan_parquet(p)
            if rid_col:
                lf = lf.filter(pl.col(rid_col) == GIJON_RADIAL)
            agg = (
                lf.group_by(est_col)
                .agg(pl.len().alias("n"))
                .collect()
            )
            for row in agg.iter_rows(named=True):
                key = str(row[est_col])
                out[key] += int(row["n"])
        return out

    clean_c = _counts_by_station(clean_paths)
    anom_c = _counts_by_station(anom_paths)
    keys = set(clean_c) | set(anom_c)
    return {k: (clean_c.get(k, 0), anom_c.get(k, 0)) for k in keys}


def _gijon_station_counts_pandas(run_root: Path) -> dict[str, tuple[int, int]]:
    import pandas as pd

    data_dir = run_root / "data"
    clean_paths, anom_paths = _iter_clean_anomaly_parquets(data_dir)

    def _one(paths: list[Path]) -> Counter[str]:
        c: Counter[str] = Counter()
        for p in paths:
            df = pd.read_parquet(p)
            df.columns = [str(x).lower() for x in df.columns]
            if "radial_id" in df.columns:
                df = df[df["radial_id"] == GIJON_RADIAL]
            if "estacion" not in df.columns:
                continue
            for est, grp in df.groupby("estacion", dropna=True):
                c[str(est)] += len(grp)
        return c

    clean_c = _one(clean_paths)
    anom_c = _one(anom_paths)
    keys = set(clean_c) | set(anom_c)
    return {k: (clean_c.get(k, 0), anom_c.get(k, 0)) for k in keys}


def _pick_chart_run(latest: RunRecord | None) -> RunRecord | None:
    """Usa la última corrida si tiene Parquet limpio y datos de Gijón."""
    if latest is None or latest.n_clean_rows <= 0:
        return None
    if _gijon_station_counts(latest.path):
        return latest
    return None


def _write_gijon_chart(station_data: dict[str, tuple[int, int]], *, run_id: str) -> bool:
    if not station_data:
        return False
    import matplotlib.pyplot as plt

    ranked = sorted(
        station_data.items(),
        key=lambda x: x[1][0] + x[1][1],
        reverse=True,
    )[:TOP_STATIONS]
    labels = [f"E{lab}" if lab.isdigit() else str(lab) for lab, _ in ranked]
    clean_vals = [v[0] for _, v in ranked]
    anom_vals = [v[1] for _, v in ranked]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(labels))
    w = 0.38
    ax.bar([i - w / 2 for i in x], clean_vals, width=w, label="Filas limpias", color="#2b6cb0")
    ax.bar([i + w / 2 for i in x], anom_vals, width=w, label="Filas anómalas", color="#c53030")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel("Número de filas (niveles CTD)")
    ax.set_title(f"Gijón — filas limpias vs anómalas por estación\n(corrida {run_id})")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150)
    plt.close(fig)
    return True


def _build_markdown(
    latest: RunRecord | None,
    *,
    n_historical_runs: int,
    quarantine_reasons: Counter[str],
    ingest_failures: list[dict[str, Any]],
    ingest_failure_reasons: Counter[str],
    ingest_failures_n: int,
    chart_run: RunRecord | None,
    chart_written: bool,
) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Informe de auditoría — última corrida — IEO-Orchestrator",
        "",
        f"*Generado: {now} · Solo lectura · `python scripts/audit_report.py`*",
        "",
        "## Nota metodológica",
        "",
        "El informe refleja **solo la corrida más reciente** en `outputs/runs/` "
        "(orden por `generated_at_utc` en `run_summary.json`). "
        f"Hay **{n_historical_runs}** corrida(s) con resumen en disco; las anteriores no se suman aquí.",
        "",
    ]

    if latest is None:
        lines.append("_No se encontró ninguna corrida en `outputs/runs/`._")
        lines.append("")
        return "\n".join(lines)

    n_clean = latest.n_clean_rows
    n_anom = latest.n_anomaly_rows
    exit_c = latest.summary.get("exit_code", "?")
    generated = latest.summary.get("generated_at_utc") or "—"
    steps_ok = latest.summary.get("steps_ok") or []
    steps_failed = latest.summary.get("steps_failed") or []

    lines.extend(
        [
            "## Corrida auditada",
            "",
            f"- **run_id:** `{latest.run_id}`",
            f"- **Generada (UTC):** {generated}",
            f"- **Código de salida:** {exit_c}",
            f"- **Pasos OK:** {', '.join(steps_ok) if steps_ok else '—'}",
        ]
    )
    if steps_failed:
        lines.append(f"- **Pasos con aviso/fallo:** {', '.join(steps_failed)}")
    lines.append("")

    funnel_rows = _build_file_funnel(latest)
    lines.extend(_format_funnel_markdown(funnel_rows))

    chk = latest.path / "checkpoints"
    if chk.is_dir():
        lines.append(
            f"Detalle ampliado en `{chk.relative_to(ROOT).as_posix()}/` "
            "(p. ej. `00_gate_rejected_detail.json`, `01_ingestion_failed_detail.json`)."
        )
        lines.append("")

    lines.extend(
        [
            "## Filas CTD y duración",
            "",
            "| Métrica | Valor |",
            "|---------|------:|",
            f"| **Filas en Parquet limpio** (`*_ctd_clean`) | **{n_clean:,}** |",
            f"| **Filas en Parquet anómalas** (`*_ctd_anomalies`) | **{n_anom:,}** |",
            f"| Tiempo de ejecución (provenance → resumen) | "
            f"{_format_duration(latest.duration_s)} |",
            "",
        ]
    )

    if n_clean + n_anom > 0:
        pct = 100.0 * n_anom / (n_clean + n_anom)
        lines.append(
            f"Proporción de filas marcadas como anómalas (Isolation Forest): "
            f"**{pct:.2f}%** ({n_anom:,} / {n_clean + n_anom:,})."
        )
        lines.append("")

    lines.extend(["## Motivos principales de cuarentena (paso 00)", ""])
    if quarantine_reasons:
        lines.append("| Motivo (agrupado) | Ocurrencias |")
        lines.append("|-------------------|------------:|")
        for reason, count in quarantine_reasons.most_common(15):
            safe = reason.replace("|", "\\|")
            lines.append(f"| {safe} | {count} |")
    else:
        lines.append("_Sin entradas en `motivos_cuarentena` de esta corrida._")
    lines.append("")

    lines.extend(["## Fallos de ingesta tras puerta (paso 01)", ""])
    if ingest_failures_n > 0:
        ingest_d = _ingest_dict(latest.summary)
        detail_name = ingest_d.get("ingestion_failed_detail_json") or "01_ingestion_failed_detail.json"
        detail_path = latest.path / "checkpoints" / str(detail_name)
        lines.append(
            f"**{ingest_failures_n}** ficheros pasaron la puerta pero no generaron Parquet canónico. "
            "No se copian a `data/quarantine/`; el `.cnv` original sigue en `data/cnv/`."
        )
        if detail_path.is_file():
            lines.append(
                f"Listado completo (ruta, motivo): "
                f"`outputs/runs/{latest.run_id}/checkpoints/{detail_name}`."
            )
        elif len(ingest_failures) < ingest_failures_n:
            lines.append(
                f"Solo hay **{len(ingest_failures)}** entradas en el checkpoint antiguo "
                f"(`01_ingestion.metrics.json`, máx. 40). Vuelve a ejecutar el pipeline para "
                f"generar `{detail_name}` con los {ingest_failures_n} ficheros."
            )
        else:
            lines.append(
                f"Listado en `outputs/runs/{latest.run_id}/checkpoints/{detail_name}` "
                "(o derivado del checkpoint de ingesta)."
            )
        lines.append("")
        if ingest_failure_reasons:
            lines.append("| Motivo (agrupado) | Ocurrencias |")
            lines.append("|-------------------|------------:|")
            for reason, count in ingest_failure_reasons.most_common(15):
                safe = str(reason).replace("|", "\\|")
                lines.append(f"| {safe} | {count} |")
        else:
            lines.append("_Motivos no disponibles en `run_summary` (regenera el pipeline para agruparlos)._")
        lines.append("")
    else:
        lines.append("_Ningún fallo de ingesta tras puerta en esta corrida._")
        lines.append("")

    lines.extend(["## Gráfico — radial Gijón", ""])
    if chart_written and chart_run:
        lines.append(
            f"Barras por estación en la misma corrida **`{chart_run.run_id}`**."
        )
        lines.append("")
        lines.append(f"![Filas limpias vs anómalas Gijón]({OUT_PNG.name})")
    else:
        lines.append(
            "_No se pudo generar el gráfico (sin Parquet con `radial_id=gijon` y columna `estacion`)._"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    latest, n_runs = _load_latest_run()
    quarantine_reasons = _collect_quarantine_reasons(latest)
    ingest = _ingest_dict(latest.summary) if latest else {}
    ingest_failures = _load_ingestion_failures(latest.path, ingest) if latest else []
    ingest_failure_reasons = _ingest_failure_reasons(ingest, ingest_failures)
    ingest_failures_n = _ingest_int(latest.summary, "n_error_tras_puerta") if latest else 0
    if ingest_failures_n == 0 and ingest_failures:
        ingest_failures_n = len(ingest_failures)
    chart_run = _pick_chart_run(latest)
    chart_written = False
    if chart_run:
        station_data = _gijon_station_counts(chart_run.path)
        chart_written = _write_gijon_chart(station_data, run_id=chart_run.run_id)

    md = _build_markdown(
        latest,
        n_historical_runs=n_runs,
        quarantine_reasons=quarantine_reasons,
        ingest_failures=ingest_failures,
        ingest_failure_reasons=ingest_failure_reasons,
        ingest_failures_n=ingest_failures_n,
        chart_run=chart_run,
        chart_written=chart_written,
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")

    if latest:
        print(f"[audit] Última corrida: {latest.run_id} ({n_runs} en disco)")
    else:
        print("[audit] Sin corridas en outputs/runs/")
    print(f"[audit] Informe Markdown: {OUT_MD}")
    if chart_written:
        print(f"[audit] Gráfico Gijón: {OUT_PNG}")
    else:
        print("[audit] Gráfico Gijón: omitido (sin datos)")
    return 0 if latest else 1


if __name__ == "__main__":
    sys.exit(main())

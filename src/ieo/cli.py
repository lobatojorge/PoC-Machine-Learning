from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ieo.io.excel_reader import ExcelReader
from ieo.io.netcdf_reader import NetCDFReader
from ieo.cnv_layout import non_year_shard_counts
from ieo.cnv_preflight import run_cnv_preflight
from ieo.paths import cnv_dir, cnv_file_label_under_root
from ieo.io.cnv_radial import classify_cnv_radial, filter_paths_by_radial
from ieo.pipeline_env import (
    PIPELINE_RADIAL_ENV,
    allowed_pipeline_radials_csv,
    resolve_pipeline_scope,
)
from ieo.ingest_gate import evaluate_file
from ieo.io.cnv_reader import CnvReader
from ieo.radiales_catalog import RADIAL_ID_CUDILLERO
from ieo.pipeline_cache import (
    build_stem_to_source_key,
    entry_matches_file,
    incremental_enabled,
    load_manifest,
    publish_canonical_to_cache,
    publish_qc_to_cache,
    resolve_file_sha256,
    save_manifest,
    try_copy_cached_canonical,
    try_copy_cached_qc_triplet,
)
from ieo.pipeline_qc import resolve_qc_workers, run_qc_batch
from ieo.reports.html_report import StepReport, write_step_report
from ieo.reports.console_progress import ProgressBar
from ieo.reports.console_run import PipelineConsole
from ieo.reports.resumen_ultima import write_resumen_ultima_html
from ieo.reports.logbook import write_logbook
from ieo.radial_labels import label_es
from ieo.runtime.paths import RunPaths
from ieo.runtime.provenance import build_provenance, write_provenance_json
from ieo.runtime.run_id import RunId, new_run_id
from ieo.transform.pipeline import PipelineConfig, ReaderFactory, build_canonical_lazyframe, write_parquet


def _ingest_stats_template() -> dict[str, Any]:
    return {
        "n_cnv_encontrados": 0,
        "n_cudillero_candidatos": 0,
        "n_omitidas_otra_radial": 0,
        "omitidas_por_radial": {},
        "muestra_omitidas_radial": [],
        "inventario_por_radial": {},
        "inventario_total": 0,
        "n_puerta_ok": 0,
        "n_cuarentena": 0,
        "n_parquet_canonicos": 0,
        "n_canonical_reutilizados": 0,
        "n_canonical_nuevos": 0,
        "n_qc_desde_cache": 0,
        "n_error_tras_puerta": 0,
        "ingestion_failed_detail_json": None,
        "motivos_error_ingesta": {},
        "muestra_error_ingesta": [],
        "copias_a_data_checked": 0,
        "motivos_cuarentena": {},
        "muestra_cuarentena": [],
        "cnv_non_year_shard_counts": {},
        "n_cnv_non_year_shards": 0,
        "cnv_preflight_summary": None,
        "filtro_radial": "todas",
        "nota_data_checked": (
            "Por defecto **todas** las radiales en `data/cnv/` siguen la **misma** cadena: "
            "control previo → Parquet → contrato → Isolation Forest. "
            "El visor prioriza ese Parquet (misma auditoría). "
            f"Alcance opcional: `{PIPELINE_RADIAL_ENV}=cudillero|gijon|santander|coruna|vigo` "
            "(menos CPU). Compatibilidad: `IEO_ONLY_CUDILLERO=1` equivale a "
            f"`{PIPELINE_RADIAL_ENV}=cudillero`. `IEO_ALL_RADIALS=1` es redundante con el valor por defecto. "
            "Lotes bajo carpetas sin año: `python run/preflight_cnv.py` o `IEO_CNV_PREFLIGHT=1` al ejecutar el pipeline."
        ),
    }


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _short_ingest_error_label(exc: BaseException) -> str:
    """Etiqueta corta para agrupar motivos de fallo en ingesta (sin copiar el .cnv)."""
    msg = str(exc)
    if "Faltan columnas requeridas" in msg and "estacion" in msg:
        return "Falta columna estación tras normalización"
    if "No se encontraron datos tras la cabecera" in msg:
        return "Sin datos tras cabecera (*END*)"
    if "no contiene filas de datos válidas" in msg:
        return "Sin filas de datos numéricas válidas"
    if "ninguna fila" in msg.lower() and "radial" in msg.lower():
        return "Filtro radial dejó 0 filas"
    if "No se encontraron columnas en la cabecera" in msg:
        return "Cabecera sin columnas al leer datos"
    if len(msg) > 120:
        return f"{type(exc).__name__}: {msg[:117]}…"
    return f"{type(exc).__name__}: {msg}"


def _write_run_summary(
    run_root: Path,
    *,
    project_root: Path,
    run_id: str,
    exit_code: int,
    steps_ok: list[str],
    steps_failed: list[str],
    artifacts: dict[str, str],
    quarantine: list[str],
    contract_errors: int,
    n_anomalies: int,
    ingest: dict[str, Any] | None = None,
    fatal_error: str | None = None,
) -> Path:
    """Escribe ``run_summary.json`` y actualiza ``outputs/RESUMEN_ULTIMA.html``."""
    summary: dict[str, Any] = {
        "run_id": run_id,
        "exit_code": exit_code,
        "steps_ok": steps_ok,
        "steps_failed": steps_failed,
        "artifacts": artifacts,
        "quarantine": quarantine,
        "contract_errors": contract_errors,
        "n_anomalies": n_anomalies,
        "ingest": ingest or _ingest_stats_template(),
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
    }
    if fatal_error:
        summary["fatal_error"] = fatal_error
    out = run_root / "run_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_resumen_ultima_html(project_root=project_root, run_root=run_root, summary=summary)
    return out


def _apply_source_radial_row_filter(
    lf: Any,
    source: Path,
    *,
    filtro_radial: str,
) -> tuple[Any, list[str]]:
    """
    Alinea filas del LazyFrame canónico con la radial del fichero / alcance del pipeline.

    - ``filtro_radial == \"todas\"``: filtra por ``classify_cnv_radial(source)`` cuando exista;
      si no, heurísticas documentadas (sin vaciar datos ambiguos).
    - ``filtro_radial == \"cudillero\"`` (alcance Cudillero): conserva el criterio histórico E1CU/E2CU/E3CU.
    - Otro id (``gijon``, …): filas con ``radial_id`` igual al alcance (misma cadena de ingesta que el resto).
    """
    import polars as pl

    from ieo.pipeline_env import ALLOWED_PIPELINE_RADIAL_IDS

    names = lf.collect_schema().names()

    if filtro_radial == "todas":
        if "radial_id" not in names:
            return lf, [
                "Columna 'radial_id' no presente; sin filtro por fila (se conservan todas las filas)."
            ]
        rid_path = classify_cnv_radial(source)
        if rid_path:
            n_total = lf.select(pl.len()).collect().item()
            lf_out = lf.filter(pl.col("radial_id") == rid_path)
            n_kept = lf_out.select(pl.len()).collect().item()
            n_dropped = n_total - n_kept
            if n_kept == 0:
                raise ValueError(
                    f"El fichero está clasificado como radial '{rid_path}' desde ruta/cabecera, "
                    "pero ninguna fila del canónico tiene esa radial_id. Revisa metadatos SeaBird."
                )
            lines = [
                f"Filtro por radial del fichero ('{rid_path}'): {n_kept:,} filas conservadas, "
                f"{n_dropped:,} descartadas (otras radiales en el mismo .cnv, si las hubiera)."
            ]
            return lf_out, lines

        distinct = (
            lf.select(pl.col("radial_id").drop_nulls().unique())
            .collect()
            .get_column("radial_id")
            .to_list()
        )
        non_null = [str(x) for x in distinct if x]
        if len(non_null) == 1:
            only = non_null[0]
            n_kept = lf.select(pl.len()).collect().item()
            return lf, [
                f"Radial del fichero no inferida en ruta; datos con una sola radial_id ({only}), "
                f"{n_kept:,} filas (sin recorte adicional)."
            ]
        return lf, [
            "Radial del fichero no inferida en ruta; varias radial_id en datos o ninguna — "
            "se conservan todas las filas para no descartar datos sin clasificar."
        ]

    if "radial_id" not in names:
        if filtro_radial == "cudillero":
            return lf, [
                "Columna 'radial_id' no presente; filtro omitido (alcance Cudillero: datos asumidos coherentes)."
            ]
        return lf, [
            f"Columna 'radial_id' no presente; sin filtro por fila (alcance pipeline: {filtro_radial})."
        ]

    if filtro_radial == "cudillero":
        distinct = (
            lf.select(pl.col("radial_id").drop_nulls().unique())
            .collect()
            .get_column("radial_id")
            .to_list()
        )
        non_null = [str(x) for x in distinct if x]
        if not non_null:
            est_note = ""
            if "estacion" in names:
                est_vals = (
                    lf.select(pl.col("estacion").drop_nulls().unique())
                    .collect()
                    .get_column("estacion")
                    .to_list()
                )
                est_note = f" Estaciones en datos: {est_vals[:8]}."
            return lf, [
                "Sin acrónimo E1CU/E2CU/E3CU en cast; filtro por radial_id omitido."
                + est_note
            ]

        n_total = lf.select(pl.len()).collect().item()
        lf_out = lf.filter(pl.col("radial_id") == RADIAL_ID_CUDILLERO)
        n_kept = lf_out.select(pl.len()).collect().item()
        n_dropped = n_total - n_kept
        lines = [
            f"Filtro alcance Cudillero ('{RADIAL_ID_CUDILLERO}'): {n_kept:,} filas conservadas, "
            f"{n_dropped:,} descartadas (otras radiales)."
        ]
        if n_kept == 0:
            raise ValueError(
                f"Tras filtrar a radial '{RADIAL_ID_CUDILLERO}' no quedan filas. "
                "Comprueba acrónimos E1CU/E2CU/E3CU o revisa el fichero."
            )
        return lf_out, lines

    if filtro_radial not in ALLOWED_PIPELINE_RADIAL_IDS:
        return lf, [f"Alcance radial '{filtro_radial}' no reconocido; sin filtro por fila."]

    n_total = lf.select(pl.len()).collect().item()
    lf_out = lf.filter(pl.col("radial_id") == filtro_radial)
    n_kept = lf_out.select(pl.len()).collect().item()
    n_dropped = n_total - n_kept
    lines = [
        f"Filtro alcance pipeline ('{filtro_radial}'): {n_kept:,} filas conservadas, "
        f"{n_dropped:,} descartadas (otras radiales en el mismo .cnv, si las hubiera)."
    ]
    if n_kept == 0:
        raise ValueError(
            f"Tras filtrar a radial '{filtro_radial}' no quedan filas. "
            "Comprueba metadatos SeaBird o el alcance IEO_PIPELINE_RADIAL."
        )
    return lf_out, lines


def _lazy_concat_parquets(paths: list[Path], out: Path) -> None:
    """Consolida muchos Parquet sin cargarlos todos en RAM de una vez."""
    import polars as pl

    if len(paths) == 1:
        shutil.copy2(paths[0], out)
        return
    try:
        pl.concat(
            [pl.scan_parquet(p) for p in paths],
            how="diagonal",
        ).collect(streaming=True).write_parquet(out)
    except TypeError:
        pl.concat([pl.scan_parquet(p) for p in paths], how="diagonal").collect().write_parquet(out)


def _consolidate_anomaly_parquets(*, run_data_dir: Path, clean_paths: list[Path]) -> Path | None:
    """Escribe ``perfiles_all.ctd_anomalies.parquet`` alineado con los clean consolidados."""
    if not clean_paths:
        return None

    anom_paths: list[Path] = []
    for cp in clean_paths:
        ap = run_data_dir / cp.name.replace("ctd_clean", "ctd_anomalies")
        if ap.is_file():
            anom_paths.append(ap)
    if not anom_paths:
        return None
    out = run_data_dir / "perfiles_all.ctd_anomalies.parquet"
    _lazy_concat_parquets(anom_paths, out)
    return out


def _consolidate_clean_parquets(*, run_data_dir: Path, clean_paths: list[Path]) -> Path | None:
    """Escribe ``perfiles_all.ctd_clean.parquet`` para el visor Streamlit."""
    if not clean_paths:
        return None

    out = run_data_dir / "perfiles_all.ctd_clean.parquet"
    _lazy_concat_parquets(clean_paths, out)
    return out


def _env_int(name: str, default: int | None = None) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _detect_sources(project_root: Path) -> list[Path]:
    """
    Detecta ficheros `.cnv` en ``data/cnv/`` y todas sus subcarpetas.

    Los ficheros ya superaron el control previo (ingest_gate) en este punto.
    Se ordenan por ruta completa para reproducibilidad (año → nombre).
    """
    cnv_d = cnv_dir(project_root)
    if not cnv_d.is_dir():
        return []
    all_files = cnv_d.rglob("*")
    return sorted([f for f in all_files if f.is_file() and f.suffix.lower() == ".cnv"])


def run_pipeline(*, project_root: Path) -> int:
    run_id = new_run_id(prefix="pipeline")
    run_paths = RunPaths(project_root=project_root, run_id=run_id)
    run_paths.ensure()
    ingest_stats = _ingest_stats_template()
    console = PipelineConsole(project_root=project_root, run_id=run_id.value)
    console.banner()
    try:
        return _run_pipeline_impl(project_root, run_id, run_paths, ingest_stats, console=console)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc()
        ingest_stats["fatal_pipeline_traceback"] = tb[-12000:]
        print(f"[ieo] [fatal] {msg}", file=sys.stderr)
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=1,
            steps_ok=[],
            steps_failed=["fatal"],
            artifacts={},
            quarantine=[],
            contract_errors=0,
            n_anomalies=0,
            ingest=ingest_stats,
            fatal_error=msg,
        )
        return 1


def _run_pipeline_impl(
    project_root: Path,
    run_id: RunId,
    run_paths: RunPaths,
    ingest_stats: dict[str, Any],
    *,
    console: PipelineConsole,
) -> int:
    cnv_root = cnv_dir(project_root)
    candidates = _detect_sources(project_root)
    inv = Counter(classify_cnv_radial(p) or "desconocida" for p in candidates)
    ingest_stats["inventario_por_radial"] = dict(sorted(inv.items(), key=lambda x: (-x[1], x[0])))
    ingest_stats["inventario_total"] = len(candidates)
    ingest_stats["n_cnv_encontrados"] = len(candidates)
    gate_rejects: list[dict[str, Any]] = []
    motivos_counter: Counter[str] = Counter()

    if not candidates:
        report = StepReport(
            step_id="01_ingestion",
            title="01 · Ingesta (sin datos)",
            summary_lines=[
                "No se encontraron ficheros de entrada.",
                "Coloca ficheros .cnv en `data/cnv/` (subcarpetas por año AAAA u otras convenciones).",
            ],
            metrics={"n_sources": 0},
            errors=[],
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=2,
            steps_ok=[],
            steps_failed=["01_ingestion"],
            artifacts={},
            quarantine=[],
            contract_errors=0,
            n_anomalies=0,
            ingest=ingest_stats,
        )
        return 2

    ny_counts = non_year_shard_counts(cnv_root, candidates)
    ingest_stats["cnv_non_year_shard_counts"] = ny_counts
    ingest_stats["n_cnv_non_year_shards"] = sum(ny_counts.values())
    if _env_truthy("IEO_CNV_PREFLIGHT"):
        pf = run_cnv_preflight(project_root, mode="non_year_shards", include_per_file_rows=False)
        ingest_stats["cnv_preflight_summary"] = {
            "scan_mode": pf.get("scan_mode"),
            "n_scanned": pf.get("n_scanned"),
            "by_folder": pf.get("by_folder"),
            "questions": pf.get("questions"),
            "n_dubious_capped": pf.get("n_dubious_capped"),
            "dubious_sample": (pf.get("dubious_sample") or [])[:40],
            "gate_reasons_global": pf.get("gate_reasons_global"),
        }

    scope_radial, scope_warnings, scope_err = resolve_pipeline_scope()
    if scope_err:
        report = StepReport(
            step_id="00_env_invalid",
            title="00 · Alcance del pipeline (entorno)",
            summary_lines=[
                scope_err,
                f"Valores permitidos para `{PIPELINE_RADIAL_ENV}`: {allowed_pipeline_radials_csv()}.",
            ],
            metrics={"invalid_scope": True},
            errors=[scope_err],
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=2,
            steps_ok=[],
            steps_failed=["00_env_invalid"],
            artifacts={},
            quarantine=[],
            contract_errors=0,
            n_anomalies=0,
            ingest=ingest_stats,
        )
        return 2

    # Misma cadena de validación para todas las radiales; el alcance solo limita *cuántos* .cnv entran.
    if scope_radial:
        gate_candidates, radial_skips, omitidas_por_radial = filter_paths_by_radial(
            candidates, scope_radial, cnv_root=cnv_root
        )
        ingest_stats["filtro_radial"] = scope_radial
        ingest_stats["n_cudillero_candidatos"] = len(gate_candidates)
        ingest_stats["n_omitidas_otra_radial"] = len(candidates) - len(gate_candidates)
        ingest_stats["omitidas_por_radial"] = omitidas_por_radial
        ingest_stats["muestra_omitidas_radial"] = radial_skips  # full list
        # Write checkpoint JSON with all skipped entries
        _chk_dir = run_paths.checkpoints_dir
        _chk_dir.mkdir(parents=True, exist_ok=True)
        _skipped_path = _chk_dir / "00_radial_skipped_detail.json"
        _skipped_path.write_text(
            json.dumps(radial_skips, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _unknowns = [e for e in radial_skips if e.get("radial") == "desconocida"]
        if _unknowns:
            _unk_path = _chk_dir / "00_radial_unknown_detail.json"
            _unk_path.write_text(
                json.dumps(_unknowns, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            ingest_stats["n_radial_desconocida"] = len(_unknowns)
            ingest_stats["radial_unknown_detail_json"] = _unk_path.name
        if not gate_candidates:
            report = StepReport(
                step_id="00_radial_filter",
                title=f"00 · Filtro radial (sin {lab})",
                summary_lines=[
                    f"Se encontraron {len(candidates)} ficheros .cnv en data/cnv/, "
                    f"ninguno clasificado como radial «{scope_radial}».",
                    f"Revisa ** Cruise:** / coordenadas o ejecuta sin `{PIPELINE_RADIAL_ENV}` "
                    "(todas las radiales).",
                    f"Omitidos por radial: {omitidas_por_radial}",
                ],
                metrics={"n_total": len(candidates), "omitidas_por_radial": omitidas_por_radial},
                errors=[],
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
            _write_run_summary(
                run_paths.run_root,
                project_root=project_root,
                run_id=run_id.value,
                exit_code=2,
                steps_ok=[],
                steps_failed=["00_radial_filter"],
                artifacts={},
                quarantine=[],
                contract_errors=0,
                n_anomalies=0,
                ingest=ingest_stats,
            )
            return 2
    else:
        ingest_stats["filtro_radial"] = "todas"
        ingest_stats["n_cudillero_candidatos"] = len(candidates)
        ingest_stats["n_omitidas_otra_radial"] = 0
        ingest_stats["omitidas_por_radial"] = {}
        ingest_stats["muestra_omitidas_radial"] = []
        gate_candidates = candidates

    incremental = incremental_enabled()
    console.section_data_inputs(
        ingest=ingest_stats,
        incremental=incremental,
        n_gate_eval=len(gate_candidates),
    )
    console.section_pipeline_steps()
    console.section_progress_begin()

    # Control previo (ingest_gate): cuarentena si no cumple reglas mínimas
    sources: list[Path] = []
    quarantine_paths: list[str] = []
    gate_progress = ProgressBar()
    n_gate = len(gate_candidates)
    for gi, candidate in enumerate(gate_candidates, start=1):
        gate_progress.update(gi, n_gate, "00 · Control previo")
        gate = evaluate_file(candidate, project_root=project_root)
        if gate.accepted:
            sources.append(candidate)
            continue
        ingest_stats["n_cuarentena"] += 1
        for r in gate.reasons:
            motivos_counter[r] += 1
        fl = cnv_file_label_under_root(cnv_root, candidate)
        gate_rejects.append(
            {
                "file": candidate.name,
                "file_label": fl,
                "path": str(candidate.resolve()),
                "reasons": list(gate.reasons),
            }
        )
        if gate.quarantine_path:
            quarantine_paths.append(str(gate.quarantine_path))

    gate_progress.finish(
        "00 · Control previo",
        detail=(
            f"{len(sources)} aceptados · {len(gate_rejects)} rechazados"
            if n_gate
            else "sin ficheros"
        ),
    )

    if gate_rejects:
        chk = run_paths.checkpoints_dir
        detail_path = chk / "00_gate_rejected_detail.json"
        detail_path.write_text(
            json.dumps(gate_rejects, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        top_motivos = motivos_counter.most_common(8)
        summary_lines = [
            f"Total rechazados en esta ejecución: {len(gate_rejects)} "
            "(copiados a data/quarantine/; rutas en checkpoints).",
            f"Detalle JSON: `{detail_path.name}`.",
            "Motivos más frecuentes:",
        ]
        for reason, count in top_motivos:
            short = reason if len(reason) <= 120 else reason[:117] + "…"
            summary_lines.append(f"  · [{count}] {short}")
        gate_report = StepReport(
            step_id="00_gate_rejected",
            title="00 · Control previo — rechazos (resumen)",
            summary_lines=summary_lines,
            metrics={
                "n_rejected": len(gate_rejects),
                "motivos_top": dict(motivos_counter.most_common(40)),
                "detail_json": detail_path.name,
            },
            errors=[],
        )
        write_step_report(out_dir=chk, report=gate_report)

    console.step_done(
        "00 · Control previo",
        f"{len(sources)} aceptados · {len(gate_rejects)} en cuarentena"
        if gate_candidates
        else "sin ficheros",
    )

    ingest_stats["n_puerta_ok"] = len(sources)
    ingest_stats["motivos_cuarentena"] = dict(motivos_counter)
    ingest_stats["muestra_cuarentena"] = gate_rejects[:25]

    max_sources = _env_int("IEO_MAX_CNV")
    if max_sources is not None and max_sources > 0 and len(sources) > max_sources:
        console.step_warn(f"IEO_MAX_CNV={max_sources}: solo los primeros {max_sources} aceptados.")
        sources = sources[:max_sources]
        ingest_stats["nota_data_checked"] += (
            f" Límite activo: IEO_MAX_CNV={max_sources}."
        )

    if not sources:
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=3,
            steps_ok=[],
            steps_failed=["00_gate_rejected"],
            artifacts={},
            quarantine=quarantine_paths,
            contract_errors=0,
            n_anomalies=0,
            ingest=ingest_stats,
        )
        return 3

    ingestion_errors: list[str] = []
    ingest_failures: list[dict[str, Any]] = []
    motivos_ingesta_counter: Counter[str] = Counter()

    # Paquetes/versiones para provenance
    packages: dict[str, str] = {}
    for pkg in ("polars", "scikit-learn", "python-calamine"):
        try:
            packages[pkg] = importlib.metadata.version(pkg)
        except Exception:
            packages[pkg] = "not-installed"

    parameters: dict[str, Any] = {
        "n_sources": len(sources),
        "source_names_sample": [p.name for p in sources[:8]],
        "pipeline_filtro_radial": ingest_stats.get("filtro_radial"),
        PIPELINE_RADIAL_ENV: os.environ.get(PIPELINE_RADIAL_ENV, "").strip() or None,
    }

    prov = build_provenance(
        run_id=run_id,
        input_files=sources,
        parameters=parameters,
        packages=packages,
        max_hash_files=50 if len(sources) > 50 else None,
    )
    write_provenance_json(run_paths.run_root / "provenance.json", prov)
    ingest_progress = ProgressBar()

    manifest = load_manifest(project_root)
    source_labels = {src: cnv_file_label_under_root(cnv_root, src) for src in sources}
    stem_to_key = build_stem_to_source_key(sources, cnv_root, source_labels)

    # Lectores (solo .cnv vía CnvReader en el flujo actual)
    factory = ReaderFactory(cnv=CnvReader(), excel=ExcelReader(), netcdf=NetCDFReader())
    config = PipelineConfig()

    # Ingesta y artefacto canónico por cada source
    canonical_paths: list[Path] = []
    n_sources = len(sources)
    for idx, src in enumerate(sources, start=1):
        ingest_progress.update(idx, n_sources, "01 · Ingesta CTD")
        source_key = source_labels[src]
        out_parquet = run_paths.data_dir / f"{src.stem}.ctd_canonical.parquet"
        entry = (manifest.get("entries") or {}).get(source_key)
        try:
            reused = False
            if incremental and entry and entry_matches_file(src, entry):
                sha = resolve_file_sha256(src, entry)
                if try_copy_cached_canonical(
                    project_root=project_root,
                    source_key=source_key,
                    stem=src.stem,
                    entry={**entry, "sha256": sha},
                    run_canonical=out_parquet,
                ):
                    reused = True
                    ingest_stats["n_canonical_reutilizados"] += 1
                    canonical_paths.append(out_parquet)
                    ingest_stats["n_parquet_canonicos"] = len(canonical_paths)
                    entry = (manifest.get("entries") or {}).get(source_key) or entry
                    entry["sha256"] = sha
                    manifest.setdefault("entries", {})[source_key] = entry

            if not reused:
                lf, _notes = build_canonical_lazyframe(
                    source=src,
                    run_paths=run_paths,
                    factory=factory,
                    config=config,
                    run_id=run_id.value,
                )
                lf, _radial_filter_lines = _apply_source_radial_row_filter(
                    lf,
                    src,
                    filtro_radial=str(ingest_stats.get("filtro_radial", "todas")),
                )
                write_parquet(lf, out_parquet)
                sha = resolve_file_sha256(src, None)
                publish_canonical_to_cache(
                    project_root=project_root,
                    source_key=source_key,
                    stem=src.stem,
                    sha256=sha,
                    run_canonical=out_parquet,
                    manifest=manifest,
                )
                ingest_stats["n_canonical_nuevos"] += 1
                canonical_paths.append(out_parquet)
                ingest_stats["n_parquet_canonicos"] = len(canonical_paths)

        except Exception as exc:
            msg = f"{src.name}: {type(exc).__name__}: {exc}"
            ingestion_errors.append(msg)
            ingest_stats["n_error_tras_puerta"] += 1
            label = _short_ingest_error_label(exc)
            motivos_ingesta_counter[label] += 1
            ingest_failures.append(
                {
                    "file": src.name,
                    "file_label": source_labels.get(src) or src.name,
                    "path": str(src.resolve()),
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                    "reason_short": label,
                }
            )

    if ingest_failures:
        chk = run_paths.checkpoints_dir
        chk.mkdir(parents=True, exist_ok=True)
        ingest_failed_path = chk / "01_ingestion_failed_detail.json"
        ingest_failed_path.write_text(
            json.dumps(ingest_failures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        ingest_stats["ingestion_failed_detail_json"] = ingest_failed_path.name
        ingest_stats["motivos_error_ingesta"] = dict(motivos_ingesta_counter.most_common(40))
        ingest_stats["muestra_error_ingesta"] = ingest_failures[:25]
        top_ingesta = motivos_ingesta_counter.most_common(8)
        ing_fail_lines = [
            f"Total con error tras pasar la puerta: {len(ingest_failures)} "
            "(el `.cnv` original permanece en `data/cnv/`; no se copia a cuarentena).",
            f"Listado completo: `{ingest_failed_path.name}`.",
            "Motivos más frecuentes:",
        ]
        for reason, count in top_ingesta:
            short = reason if len(reason) <= 120 else reason[:117] + "…"
            ing_fail_lines.append(f"  · [{count}] {short}")
        write_step_report(
            out_dir=chk,
            report=StepReport(
                step_id="01_ingestion_failed",
                title="01 · Ingesta — fallos tras puerta (sin copia)",
                summary_lines=ing_fail_lines,
                metrics={
                    "n_failed": len(ingest_failures),
                    "motivos_top": dict(motivos_ingesta_counter.most_common(40)),
                    "detail_json": ingest_failed_path.name,
                },
                errors=ingestion_errors[:40],
            ),
        )

    save_manifest(project_root, manifest)
    ingest_detail = (
        f"{len(canonical_paths)} Parquet · {ingest_stats['n_error_tras_puerta']} errores"
    )
    if incremental:
        ingest_detail += (
            f" · {ingest_stats['n_canonical_reutilizados']} reutilizados · "
            f"{ingest_stats['n_canonical_nuevos']} nuevos"
        )
    ingest_progress.finish("01 · Ingesta CTD", detail=ingest_detail)
    console.step_done("01 · Ingesta CTD", ingest_detail)
    ing_summary = [
        f"Fuentes procesadas: {n_sources}",
        f"Parquet canónicos generados: {len(canonical_paths)}",
        f"Errores de ingesta: {len(ingestion_errors)}",
    ]
    if ingest_stats.get("ingestion_failed_detail_json"):
        ing_summary.append(
            f"Detalle de fallos (listado completo): `{ingest_stats['ingestion_failed_detail_json']}`."
        )
    ingest_report = StepReport(
        step_id="01_ingestion",
        title="01 · Ingesta (artefactos canónicos)",
        summary_lines=ing_summary,
        metrics={
            "n_sources": n_sources,
            "n_canonical": len(canonical_paths),
            "n_reused": ingest_stats.get("n_canonical_reutilizados", 0),
            "n_new": ingest_stats.get("n_canonical_nuevos", 0),
            "n_errors": len(ingestion_errors),
            "ingestion_failed_detail_json": ingest_stats.get("ingestion_failed_detail_json"),
        },
        errors=ingestion_errors[:40],
    )
    write_step_report(out_dir=run_paths.checkpoints_dir, report=ingest_report)

    if not canonical_paths:
        report = StepReport(
            step_id="01_ingestion_errors",
            title="01 · Ingesta (sin fuentes válidas)",
            summary_lines=[
                "No se pudo generar ningún artefacto canónico CTD.",
                "Revisa los ficheros `.cnv` en `data/cnv/` (cabecera SeaBird, columnas de presión/temperatura, datos tras `*END*`).",
            ],
            metrics={"n_sources": len(sources), "n_processed": 0, "n_errors": len(ingestion_errors)},
            errors=ingestion_errors,
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=1,
            steps_ok=[],
            steps_failed=["01_ingestion_errors"],
            artifacts={},
            quarantine=quarantine_paths,
            contract_errors=0,
            n_anomalies=0,
            ingest=ingest_stats,
        )
        return 1

    # ------------------------------------------------------------
    # Paso 02: Anomalías + registro inmutable (paralelo por perfil)
    # ------------------------------------------------------------
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module=r"sklearn\.utils\.parallel")

    _summary_artifacts: dict[str, str] = {}
    qc_progress = ProgressBar()
    n_canonical = len(canonical_paths)

    if incremental:
        for can_path in canonical_paths:
            stem = can_path.name.replace(".ctd_canonical.parquet", "")
            source_key = stem_to_key.get(stem)
            if not source_key:
                continue
            entry = (manifest.get("entries") or {}).get(source_key)
            if entry and try_copy_cached_qc_triplet(
                project_root=project_root,
                entry=entry,
                stem=stem,
                run_data_dir=run_paths.data_dir,
            ):
                ingest_stats["n_qc_desde_cache"] += 1

    clean_paths, step_errors, _summary_contract_errors, _summary_n_anomalies, n_qc_skipped, _n_files_contract_err = (
        run_qc_batch(
            canonical_paths=canonical_paths,
            run_data_dir=run_paths.data_dir,
            run_id=run_id.value,
            on_progress=lambda cur, tot: qc_progress.update(cur, tot, "02 · Calidad y anomalías"),
        )
    )

    if clean_paths:
        last = clean_paths[-1]
        can_last = run_paths.data_dir / last.name.replace("ctd_clean", "ctd_canonical")
        _summary_artifacts.update({
            "canonical": str(can_last),
            "clean": str(last),
            "anomalies": str(last).replace("ctd_clean", "ctd_anomalies"),
            "audit": str(last).replace("ctd_clean", "ctd_anomaly_audit"),
        })

    n_qc_ok = len(clean_paths)
    qc_detail = f"{n_qc_ok}/{n_canonical} perfiles"
    if n_qc_skipped:
        qc_detail += f" · {n_qc_skipped} reutilizados en run"
    if ingest_stats.get("n_qc_desde_cache"):
        qc_detail += f" · {ingest_stats['n_qc_desde_cache']} desde caché"
    if step_errors:
        qc_detail += f" · {len(step_errors)} fallos"
    qc_progress.finish("02 · Calidad y anomalías", detail=qc_detail)
    console.step_done("01b · Contrato + 02 · Anomalías", qc_detail)

    contract_report = StepReport(
        step_id="01b_radial_contract",
        title="01b · Contrato radial (resumen de la ejecución)",
        summary_lines=[
            f"Parquet evaluados: {n_canonical}",
            f"Errores de contrato (total filas/reglas): {_summary_contract_errors}",
            f"Ficheros con al menos un ERROR: {_n_files_contract_err}",
        ],
        metrics={
            "n_inputs": float(n_canonical),
            "n_errors": float(_summary_contract_errors),
            "n_files_with_errors": float(_n_files_contract_err),
        },
        errors=[],
    )
    write_step_report(out_dir=run_paths.checkpoints_dir, report=contract_report)
    anomalies_report = StepReport(
        step_id="02_anomalies",
        title="02 · Anomalías (Isolation Forest) — resumen",
        summary_lines=[
            f"Perfiles procesados: {n_canonical - len(step_errors)}",
            f"Filas marcadas como anomalía: {_summary_n_anomalies}",
            "Artefactos por perfil: *_ctd_clean.parquet, *_ctd_anomalies.parquet, *_ctd_anomaly_audit.parquet",
        ],
        metrics={
            "n_inputs": n_canonical,
            "n_anomalies": _summary_n_anomalies,
            "n_step_errors": len(step_errors),
        },
        errors=step_errors[:40],
    )
    write_step_report(out_dir=run_paths.checkpoints_dir, report=anomalies_report)

    if step_errors:
        err_report = StepReport(
            step_id="02_anomalies_errors",
            title="02 · Anomalías (errores parciales)",
            summary_lines=[
                f"Falló el QC en {len(step_errors)} de {n_canonical} perfiles; el resto continúa.",
                "Detalle en errors (máx. 40 listados).",
            ],
            metrics={"n_errors": len(step_errors), "n_ok": len(clean_paths)},
            errors=step_errors,
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=err_report)
        console.step_warn(
            f"QC parcial: {len(step_errors)} perfil(es) fallaron; {len(clean_paths)} listos para consolidar."
        )

    if not clean_paths:
        logbook_path = write_logbook(run_root=run_paths.run_root, run_id=run_id.value)
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=1,
            steps_ok=["01_ingestion"],
            steps_failed=["02_anomalies_errors"],
            artifacts=_summary_artifacts,
            quarantine=quarantine_paths,
            contract_errors=_summary_contract_errors,
            n_anomalies=0,
            ingest=ingest_stats,
        )
        console.section_results(
            exit_code=1,
            ingest=ingest_stats,
            steps_ok=["01_ingestion"],
            steps_failed=["02_anomalies_errors"],
            n_anomalies=0,
            contract_errors=_summary_contract_errors,
            n_quarantine=len(quarantine_paths),
            n_qc_errors=len(step_errors),
            artifacts=_summary_artifacts,
            logbook_name=logbook_path.name,
        )
        console.section_streamlit()
        console.closing_line(1)
        return 1

    for can_path in canonical_paths:
        stem = can_path.name.replace(".ctd_canonical.parquet", "")
        source_key = stem_to_key.get(stem)
        if not source_key:
            continue
        clean_p = run_paths.data_dir / f"{stem}.ctd_clean.parquet"
        if clean_p.is_file():
            publish_qc_to_cache(
                project_root=project_root,
                source_key=source_key,
                stem=stem,
                run_data_dir=run_paths.data_dir,
                manifest=manifest,
            )
    save_manifest(project_root, manifest)

    cons_progress = ProgressBar()
    cons_progress.update(1, 1, "03 · Consolidación")
    consolidated = _consolidate_clean_parquets(run_data_dir=run_paths.data_dir, clean_paths=clean_paths)
    if consolidated:
        _summary_artifacts["clean_all"] = str(consolidated)
        anom_all = _consolidate_anomaly_parquets(run_data_dir=run_paths.data_dir, clean_paths=clean_paths)
        if anom_all is not None:
            _summary_artifacts["anomalies_all"] = str(anom_all)
    cons_progress.finish(
        "03 · Consolidación",
        detail="perfiles_all.ctd_clean.parquet" if consolidated else "sin consolidado",
    )
    console.step_done(
        "03 · Consolidación",
        "perfiles_all.ctd_clean.parquet generado" if consolidated else "omitida",
    )

    logbook_path = write_logbook(run_root=run_paths.run_root, run_id=run_id.value)
    steps_ok = ["01_ingestion", "01b_radial_contract", "02_anomalies"]
    steps_failed: list[str] = ["02_anomalies_partial"] if step_errors else []
    final_exit = 0

    _write_run_summary(
        run_paths.run_root,
        project_root=project_root,
        run_id=run_id.value,
        exit_code=final_exit,
        steps_ok=steps_ok,
        steps_failed=steps_failed,
        artifacts=_summary_artifacts,
        quarantine=quarantine_paths,
        contract_errors=_summary_contract_errors,
        n_anomalies=_summary_n_anomalies,
        ingest=ingest_stats,
    )
    console.section_results(
        exit_code=final_exit,
        ingest=ingest_stats,
        steps_ok=steps_ok,
        steps_failed=steps_failed,
        n_anomalies=_summary_n_anomalies,
        contract_errors=_summary_contract_errors,
        n_quarantine=len(quarantine_paths),
        n_qc_errors=len(step_errors),
        artifacts=_summary_artifacts,
        logbook_name=logbook_path.name,
    )
    console.section_streamlit()
    console.closing_line(final_exit)
    return final_exit


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ieo", description="Pipeline IEO (producción)")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Ejecuta pipeline sobre ficheros .cnv en data/cnv/ (recursivo)")
    run.add_argument("--project-root", type=str, default=str(Path(__file__).resolve().parents[2]))
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "run":
        return run_pipeline(project_root=Path(args.project_root).resolve())
    raise RuntimeError("Comando no soportado")


if __name__ == "__main__":
    raise SystemExit(main())


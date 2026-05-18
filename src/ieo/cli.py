from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ieo.io.excel_reader import ExcelReader
from ieo.io.netcdf_reader import NetCDFReader
from ieo.cudillero_paths import cnv_dir
from ieo.io.cnv_radial import filter_paths_to_cudillero
from ieo.ingest_gate import evaluate_file
from ieo.io.cnv_reader import CnvReader
from ieo.radiales_catalog import RADIAL_ID_CUDILLERO
from ieo.observability.anomaly import IsolationForestConfig, detect_anomalies_isolation_forest
from ieo.observability.quality_summary import build_health_summary
from ieo.reports.html_report import StepReport, write_step_report
from ieo.reports.resumen_ultima import format_ingest_console, write_resumen_ultima_html
from ieo.reports.logbook import write_logbook
from ieo.runtime.paths import RunPaths
from ieo.runtime.provenance import build_provenance, write_provenance_json
from ieo.runtime.run_id import new_run_id
from ieo.transform.pipeline import PipelineConfig, ReaderFactory, build_canonical_lazyframe, dataset_metrics, write_parquet
from ieo.validation.radial_contract import ViolationSeverity, validate_canonical_ctd_polars


def _ingest_stats_template() -> dict[str, Any]:
    return {
        "n_cnv_encontrados": 0,
        "n_cudillero_candidatos": 0,
        "n_omitidas_otra_radial": 0,
        "omitidas_por_radial": {},
        "muestra_omitidas_radial": [],
        "n_puerta_ok": 0,
        "n_cuarentena": 0,
        "n_parquet_canonicos": 0,
        "n_error_tras_puerta": 0,
        "copias_a_data_checked": 0,
        "motivos_cuarentena": {},
        "muestra_cuarentena": [],
        "filtro_radial": "cudillero",
        "nota_data_checked": (
            "Entrada: data/cnv/ (todas las radiales en disco). "
            "El pipeline solo procesa ficheros clasificados como Cudillero "
            "(metadatos ** Cruise:** y nombre de fichero). "
            "IEO_ALL_RADIALS=1 desactiva el filtro."
        ),
    }


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


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
) -> Path:
    """Escribe ``run_summary.json`` y actualiza ``outputs/RESUMEN_ULTIMA.html``."""
    summary = {
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
    out = run_root / "run_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_resumen_ultima_html(project_root=project_root, run_root=run_root, summary=summary)
    return out


def _apply_cudillero_radial_filter(lf: Any) -> tuple[Any, list[str]]:
    """
    Filtra a radial Cudillero si hay ``radial_id`` inferible (E1CU/E2CU/E3CU).

    Los .cnv IEO suelen traer ``cast`` = nombre de fichero (p. ej. ``2jul601``) y
    ``** Station: 6`` en cabecera: en ese caso se conservan todas las filas.
    """
    import polars as pl

    names = lf.collect_schema().names()
    if "radial_id" not in names:
        return lf, [
            "Columna 'radial_id' no presente; filtro omitido (datos en data/cnv/ asumidos Cudillero)."
        ]

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
    lf = lf.filter(pl.col("radial_id") == RADIAL_ID_CUDILLERO)
    n_kept = lf.select(pl.len()).collect().item()
    n_dropped = n_total - n_kept
    lines = [
        f"Filtro radial '{RADIAL_ID_CUDILLERO}': {n_kept:,} filas conservadas, "
        f"{n_dropped:,} descartadas (otras radiales)."
    ]
    if n_kept == 0:
        raise ValueError(
            f"Tras filtrar a radial '{RADIAL_ID_CUDILLERO}' no quedan filas. "
            "Comprueba acrónimos E1CU/E2CU/E3CU o coloca solo ficheros Cudillero en data/cnv/."
        )
    return lf, lines


def _consolidate_clean_parquets(*, run_data_dir: Path, clean_paths: list[Path]) -> Path | None:
    """Escribe ``perfiles_all.ctd_clean.parquet`` para el visor Streamlit."""
    if not clean_paths:
        return None
    import polars as pl

    out = run_data_dir / "perfiles_all.ctd_clean.parquet"
    if len(clean_paths) == 1:
        shutil.copy2(clean_paths[0], out)
    else:
        pl.concat([pl.read_parquet(p) for p in clean_paths], how="vertical_relaxed").write_parquet(out)
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

    Los ficheros ya han pasado la puerta de cuarentena en este punto.
    Se ordenan por ruta completa para reproducibilidad (año → nombre).
    """
    cnv_d = cnv_dir(project_root)
    if not cnv_d.is_dir():
        return []
    return sorted(cnv_d.rglob("*.cnv"))


def run_pipeline(*, project_root: Path) -> int:
    run_id = new_run_id(prefix="pipeline")
    run_paths = RunPaths(project_root=project_root, run_id=run_id)
    run_paths.ensure()

    # ------------------------------------------------------------
    # Paso 00: Detectar fuentes + puerta de cuarentena por fichero
    # ------------------------------------------------------------
    candidates = _detect_sources(project_root)
    ingest_stats = _ingest_stats_template()
    ingest_stats["n_cnv_encontrados"] = len(candidates)
    gate_rejects: list[dict[str, Any]] = []
    motivos_counter: Counter[str] = Counter()

    if not candidates:
        report = StepReport(
            step_id="01_ingestion",
            title="01 · Ingesta (sin datos)",
            summary_lines=[
                "No se encontraron ficheros de entrada.",
                "Coloca ficheros .cnv en `data/cnv/` (o en subcarpetas por año).",
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

    # Solo Cudillero (omitir Gijón, Santander, Vigo, … sin pasar por cuarentena)
    if _env_truthy("IEO_ALL_RADIALS"):
        ingest_stats["filtro_radial"] = "todas"
        ingest_stats["n_cudillero_candidatos"] = len(candidates)
        gate_candidates = candidates
        print(
            f"[ieo] IEO_ALL_RADIALS=1: se evaluarán las {len(candidates)} radiales en data/cnv/.",
            file=sys.stderr,
        )
    else:
        gate_candidates, radial_skips, omitidas_por_radial = filter_paths_to_cudillero(candidates)
        ingest_stats["n_cudillero_candidatos"] = len(gate_candidates)
        ingest_stats["n_omitidas_otra_radial"] = len(candidates) - len(gate_candidates)
        ingest_stats["omitidas_por_radial"] = omitidas_por_radial
        ingest_stats["muestra_omitidas_radial"] = radial_skips
        print(
            f"[ieo] Filtro radial Cudillero: {len(gate_candidates)} de {len(candidates)} "
            f"ficheros .cnv (omitidos {ingest_stats['n_omitidas_otra_radial']} de otras radiales).",
            file=sys.stderr,
        )
        if omitidas_por_radial:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(omitidas_por_radial.items(), key=lambda x: -x[1])[:5])
            print(f"[ieo] Omitidos por radial: {parts}", file=sys.stderr)

        if not gate_candidates:
            report = StepReport(
                step_id="00_radial_filter",
                title="00 · Filtro radial (sin Cudillero)",
                summary_lines=[
                    f"Se encontraron {len(candidates)} ficheros .cnv en data/cnv/, "
                    "pero ninguno se clasificó como radial Cudillero.",
                    "Revisa ** Cruise:** en la cabecera o usa IEO_ALL_RADIALS=1 para depuración.",
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

    # Evaluar cada candidato Cudillero con la puerta de cuarentena
    sources: list[Path] = []
    quarantine_paths: list[str] = []
    for candidate in gate_candidates:
        gate = evaluate_file(candidate, project_root=project_root)
        if gate.accepted:
            sources.append(candidate)
        else:
            ingest_stats["n_cuarentena"] += 1
            for r in gate.reasons:
                motivos_counter[r] += 1
            gate_rejects.append({"file": candidate.name, "reasons": list(gate.reasons)})
            q_info = f" → copiado a `{gate.quarantine_path}`" if gate.quarantine_path else ""
            report = StepReport(
                step_id="00_gate_rejected",
                title=f"00 · Puerta de entrada (rechazado: {candidate.name})",
                summary_lines=[
                    f"El fichero `{candidate.name}` no superó la comprobación previa{q_info}.",
                    "Motivos:",
                    *[f"  - {r}" for r in gate.reasons],
                    "Corrige el fichero y vuelve a colocarlo en la carpeta correspondiente.",
                ],
                metrics={"file": str(candidate), "n_reasons": len(gate.reasons)},
                errors=gate.reasons,
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
            print(
                f"[ieo] Rechazado `{candidate.name}`: {'; '.join(gate.reasons)}",
                file=sys.stderr,
            )
            if gate.quarantine_path:
                quarantine_paths.append(str(gate.quarantine_path))

    ingest_stats["n_puerta_ok"] = len(sources)
    ingest_stats["motivos_cuarentena"] = dict(motivos_counter)
    ingest_stats["muestra_cuarentena"] = gate_rejects[:25]

    max_sources = _env_int("IEO_MAX_CNV")
    if max_sources is not None and max_sources > 0 and len(sources) > max_sources:
        print(
            f"[ieo] IEO_MAX_CNV={max_sources}: se procesarán solo los primeros "
            f"{max_sources} de {len(sources)} ficheros aceptados.",
            file=sys.stderr,
        )
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
    clean_paths: list[Path] = []

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
    }

    if len(sources) > 50:
        print(
            f"[ieo] Provenance: {len(sources)} ficheros; SHA256 solo en los primeros 50 "
            "(evita bloquear la ingesta).",
            file=sys.stderr,
        )
    prov = build_provenance(
        run_id=run_id,
        input_files=sources,
        parameters=parameters,
        packages=packages,
        max_hash_files=50 if len(sources) > 50 else None,
    )
    write_provenance_json(run_paths.run_root / "provenance.json", prov)
    print(f"[ieo] Ingesta de {len(sources)} fichero(s)…", file=sys.stderr)

    # Lectores (solo .cnv vía CnvReader en el flujo actual)
    factory = ReaderFactory(cnv=CnvReader(), excel=ExcelReader(), netcdf=NetCDFReader())
    config = PipelineConfig()

    # Ingesta y artefacto canónico por cada source
    canonical_paths: list[Path] = []
    n_sources = len(sources)
    for idx, src in enumerate(sources, start=1):
        if idx == 1 or idx % 25 == 0 or idx == n_sources:
            print(f"[ieo] Ingesta [{idx}/{n_sources}] {src.name}", file=sys.stderr)
        try:
            lf, notes = build_canonical_lazyframe(
                source=src,
                run_paths=run_paths,
                factory=factory,
                config=config,
                run_id=run_id.value,
            )
            lf, radial_filter_lines = _apply_cudillero_radial_filter(lf)

            out_parquet = run_paths.data_dir / f"{src.stem}.ctd_canonical.parquet"
            write_parquet(lf, out_parquet)
            canonical_paths.append(out_parquet)
            ingest_stats["n_parquet_canonicos"] = len(canonical_paths)

            report = StepReport(
                step_id="01_ingestion",
                title="01 · Ingesta (artefactos canónicos)",
                summary_lines=[
                    f"Fuente detectada: {src.name}",
                    "Se normalizó a una tabla estable (staging) y se escribió Parquet canónico.",
                    *radial_filter_lines,
                    *notes,
                ],
                metrics={"source": src.name, "canonical_parquet": str(out_parquet), **dataset_metrics(lf)},
                errors=[],
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        except Exception as exc:
            msg = f"{src.name}: {type(exc).__name__}: {exc}"
            ingestion_errors.append(msg)
            ingest_stats["n_error_tras_puerta"] += 1
            report = StepReport(
                step_id="01_ingestion_skipped",
                title="01 · Ingesta (fuente omitida)",
                summary_lines=[
                    f"Fuente omitida: {src.name}",
                    "Motivo: no cumple el esquema mínimo CTD o no es legible.",
                    "El pipeline continúa con el resto de fuentes.",
                ],
                metrics={"source": src.name},
                errors=[msg],
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=report)

    print(format_ingest_console(ingest_stats), file=sys.stderr)

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
    # Paso 02: Anomalías + registro inmutable (por cada canónico)
    # ------------------------------------------------------------
    try:
        import polars as pl
    except Exception as exc:  # pragma: no cover
        raise ImportError("Falta polars para ejecutar el pipeline.") from exc

    step_errors: list[str] = []
    _summary_artifacts: dict[str, str] = {}
    _summary_contract_errors = 0
    _summary_n_anomalies = 0
    anomaly_cfg = IsolationForestConfig(contamination=0.05, random_state=42, n_estimators=200)
    for can_path in canonical_paths:
        try:
            df_can = pl.read_parquet(can_path)
            # Detectar columna row_id (creada en canonical)
            row_id_col = config.schema.row_id
            if row_id_col not in df_can.columns:
                raise ValueError(f"Artefacto canónico sin `{row_id_col}`: {can_path.name}")

            cv = validate_canonical_ctd_polars(df_can)
            n_contract_err = sum(1 for v in cv if v.severity == ViolationSeverity.ERROR)
            _summary_contract_errors += n_contract_err
            contract_lines = [f"{v.severity.value}:{v.code}: {v.message}" for v in cv[:25]]
            contract_report = StepReport(
                step_id="01b_radial_contract",
                title="01b · Contrato radial (rangos físicos en perfil CTD)",
                summary_lines=[
                    "Validación sobre columnas canónicas (temperatura/profundidad por fila).",
                    f"Total violaciones: {len(cv)} (errores: {n_contract_err}).",
                    *contract_lines,
                ],
                metrics={
                    "input": can_path.name,
                    "n_violations": float(len(cv)),
                    "n_errors": float(n_contract_err),
                    "codes": [v.code for v in cv],
                },
                errors=[v.message for v in cv if v.severity == ViolationSeverity.ERROR],
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=contract_report)
            if n_contract_err:
                print(
                    f"[ieo] Contrato radial: {n_contract_err} ERROR(s) en {can_path.name} "
                    "(ver checkpoints/01b_radial_contract*.html)",
                    file=sys.stderr,
                )

            outs = detect_anomalies_isolation_forest(
                df=df_can,
                row_id_col=row_id_col,
                config=anomaly_cfg,
                run_id=run_id.value,
                source_file=can_path.name,
            )

            clean_path = run_paths.data_dir / can_path.name.replace("ctd_canonical", "ctd_clean")
            anom_path = run_paths.data_dir / can_path.name.replace("ctd_canonical", "ctd_anomalies")
            audit_path = run_paths.data_dir / can_path.name.replace("ctd_canonical", "ctd_anomaly_audit")
            outs.clean.write_parquet(clean_path)
            clean_paths.append(clean_path)
            outs.anomalies.write_parquet(anom_path)
            outs.audit_log.write_parquet(audit_path)
            _summary_n_anomalies += len(outs.anomalies)
            _summary_artifacts.update({
                "canonical": str(can_path),
                "clean": str(clean_path),
                "anomalies": str(anom_path),
                "audit": str(audit_path),
            })

            # Paso 03: salud del dataset (resumen para no técnicos)
            health = build_health_summary(
                canonical=df_can,
                clean=outs.clean,
                anomalies=outs.anomalies,
                audit_log=outs.audit_log,
            )
            q_report = StepReport(
                step_id="03_quality",
                title="03 · Reporte de calidad (salud del dataset)",
                summary_lines=[
                    "Este resumen está pensado para entender rápidamente si el dataset está 'sano'.",
                    "Incluye cuántas filas entraron, cuántas se limpiaron y cuántas se marcaron como sospechosas.",
                ],
                metrics={"input": can_path.name, **health.metrics},
                errors=[],
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=q_report)

            report = StepReport(
                step_id="02_anomalies",
                title="02 · Anomalías (Isolation Forest) + registro inmutable",
                summary_lines=[
                    f"Entrada canónica: {can_path.name}",
                    "Se ejecutó Isolation Forest con semilla fija (reproducible).",
                    "Se generaron 3 artefactos: clean, anomalies y audit_log (inmutable).",
                ],
                metrics={
                    "input": can_path.name,
                    "clean_parquet": str(clean_path),
                    "anomalies_parquet": str(anom_path),
                    "audit_parquet": str(audit_path),
                    **outs.metrics,
                },
                errors=[],
            )
            write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        except Exception as exc:
            step_errors.append(f"{can_path.name}: {type(exc).__name__}: {exc}")

    if step_errors:
        report = StepReport(
            step_id="02_anomalies_errors",
            title="02 · Anomalías (errores)",
            summary_lines=["Falló la detección de anomalías para uno o más artefactos canónicos."],
            metrics={"n_errors": len(step_errors)},
            errors=step_errors,
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        logbook_path = write_logbook(run_root=run_paths.run_root, run_id=run_id.value)
        print(f"[ieo] Cuaderno de bitácora: {logbook_path}", file=sys.stderr)
        _write_run_summary(
            run_paths.run_root,
            project_root=project_root,
            run_id=run_id.value,
            exit_code=1,
            steps_ok=["01_ingestion", "01b_radial_contract"],
            steps_failed=["02_anomalies_errors"],
            artifacts=_summary_artifacts,
            quarantine=quarantine_paths,
            contract_errors=_summary_contract_errors,
            n_anomalies=_summary_n_anomalies,
            ingest=ingest_stats,
        )
        return 1

    consolidated = _consolidate_clean_parquets(run_data_dir=run_paths.data_dir, clean_paths=clean_paths)
    if consolidated:
        _summary_artifacts["clean_all"] = str(consolidated)
        anom_all = run_paths.data_dir / "perfiles_all.ctd_anomalies.parquet"
        if len(clean_paths) == 1:
            src_anom = clean_paths[0].name.replace("ctd_clean", "ctd_anomalies")
            single_anom = run_paths.data_dir / src_anom
            if single_anom.is_file():
                shutil.copy2(single_anom, anom_all)
                _summary_artifacts["anomalies_all"] = str(anom_all)

    logbook_path = write_logbook(run_root=run_paths.run_root, run_id=run_id.value)
    print(f"[ieo] Cuaderno de bitácora: {logbook_path}", file=sys.stderr)
    summary_path = _write_run_summary(
        run_paths.run_root,
        project_root=project_root,
        run_id=run_id.value,
        exit_code=0,
        steps_ok=["01_ingestion", "01b_radial_contract", "02_anomalies", "03_quality"],
        steps_failed=[],
        artifacts=_summary_artifacts,
        quarantine=quarantine_paths,
        contract_errors=_summary_contract_errors,
        n_anomalies=_summary_n_anomalies,
        ingest=ingest_stats,
    )
    print(format_ingest_console(ingest_stats), file=sys.stderr)
    resumen_html = project_root / "outputs" / "RESUMEN_ULTIMA.html"
    leeme = project_root / "outputs" / "LEEME_RESUMEN.txt"
    print(f"[ieo] Resumen de corrida: {summary_path}", file=sys.stderr)
    if resumen_html.is_file():
        print(f"[ieo] Resumen visual HTML: {resumen_html.resolve()}", file=sys.stderr)
    if leeme.is_file():
        print(f"[ieo] Puntero al HTML: {leeme.resolve()}", file=sys.stderr)
    return 0


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


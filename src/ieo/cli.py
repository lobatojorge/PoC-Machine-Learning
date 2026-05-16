from __future__ import annotations

import argparse
import importlib.metadata
import sys
from pathlib import Path
from typing import Any

from ieo.io.excel_reader import ExcelReader
from ieo.io.netcdf_reader import NetCDFReader
from ieo.cudillero_paths import default_radial_csv_path
from ieo.io.radial_csv_reader import RadialCsvReader
from ieo.radiales_catalog import RADIAL_ID_CUDILLERO
from ieo.observability.anomaly import IsolationForestConfig, detect_anomalies_isolation_forest
from ieo.observability.quality_summary import build_health_summary
from ieo.reports.html_report import StepReport, write_step_report
from ieo.reports.logbook import write_logbook
from ieo.runtime.paths import RunPaths
from ieo.runtime.provenance import build_provenance, write_provenance_json
from ieo.runtime.run_id import new_run_id
from ieo.transform.pipeline import PipelineConfig, ReaderFactory, build_canonical_lazyframe, dataset_metrics, write_parquet
from ieo.validation.radial_contract import ViolationSeverity, validate_canonical_ctd_polars


def _detect_sources(project_root: Path) -> list[Path]:
    """
    Entrada única: CSV radial Cudillero en `data/processed/perfiles_all.csv`.
    No se escanea `data/raw/` (respaldo local, fuera del pipeline).
    """
    p = default_radial_csv_path(project_root)
    return [p] if p.is_file() else []


def run_pipeline(*, project_root: Path) -> int:
    run_id = new_run_id(prefix="pipeline")
    run_paths = RunPaths(project_root=project_root, run_id=run_id)
    run_paths.ensure()

    csv_path = default_radial_csv_path(project_root)

    sources = _detect_sources(project_root)
    ingestion_errors: list[str] = []

    if not sources:
        report = StepReport(
            step_id="01_ingestion",
            title="01 · Ingesta (sin datos)",
            summary_lines=[
                f"No existe el CSV radial esperado: `{csv_path}`.",
                "Coloca `perfiles_all.csv` en `data/processed/`.",
                "Nota: `data/raw/` no se lee en el pipeline (solo respaldo local).",
            ],
            metrics={"csv_path": str(csv_path), "n_sources": 0},
            errors=[],
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        return 2

    # Paquetes/versiones para provenance
    packages: dict[str, str] = {}
    for pkg in ("polars", "scikit-learn", "python-calamine"):
        try:
            packages[pkg] = importlib.metadata.version(pkg)
        except Exception:
            packages[pkg] = "not-installed"

    parameters: dict[str, Any] = {
        "sources": [p.name for p in sources],
    }

    prov = build_provenance(run_id=run_id, input_files=sources, parameters=parameters, packages=packages)
    write_provenance_json(run_paths.run_root / "provenance.json", prov)

    # Lectores
    factory = ReaderFactory(csv=RadialCsvReader(), excel=ExcelReader(), netcdf=NetCDFReader())
    config = PipelineConfig()

    # Ingesta y artefacto canónico por cada source
    canonical_paths: list[Path] = []
    for src in sources:
        try:
            lf, notes = build_canonical_lazyframe(
                source=src,
                run_paths=run_paths,
                factory=factory,
                config=config,
                run_id=run_id.value,
            )
            # Filtro de radial: solo Cudillero (E1CU, E2CU, E3CU)
            radial_filter_lines: list[str] = []
            if "radial_id" in lf.collect_schema().names():
                import polars as _pl  # noqa: PLC0415
                n_total = lf.select(_pl.len()).collect().item()
                lf = lf.filter(_pl.col("radial_id") == RADIAL_ID_CUDILLERO)
                n_kept = lf.select(_pl.len()).collect().item()
                n_dropped = n_total - n_kept
                radial_filter_lines = [
                    f"Filtro radial '{RADIAL_ID_CUDILLERO}': {n_kept:,} filas conservadas, "
                    f"{n_dropped:,} descartadas (otras radiales).",
                ]
                if n_kept == 0:
                    raise ValueError(
                        f"Tras filtrar a radial '{RADIAL_ID_CUDILLERO}' no quedan filas. "
                        "Comprueba que el CSV contiene datos con acrónimos E1CU/E2CU/E3CU."
                    )
            else:
                radial_filter_lines = ["Columna 'radial_id' no presente; filtro de radial omitido."]

            out_parquet = run_paths.data_dir / f"{src.stem}.ctd_canonical.parquet"
            write_parquet(lf, out_parquet)
            canonical_paths.append(out_parquet)

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

    if not canonical_paths:
        report = StepReport(
            step_id="01_ingestion_errors",
            title="01 · Ingesta (sin fuentes válidas)",
            summary_lines=[
                "No se pudo generar ningún artefacto canónico CTD.",
                f"Revisa el CSV (`{default_radial_csv_path(project_root)}`) y columnas mínimas (fecha, estación, profundidad, temperatura).",
            ],
            metrics={"n_sources": len(sources), "n_processed": 0, "n_errors": len(ingestion_errors)},
            errors=ingestion_errors,
        )
        write_step_report(out_dir=run_paths.checkpoints_dir, report=report)
        return 1

    # ------------------------------------------------------------
    # Paso 02: Anomalías + registro inmutable (por cada canónico)
    # ------------------------------------------------------------
    try:
        import polars as pl
    except Exception as exc:  # pragma: no cover
        raise ImportError("Falta polars para ejecutar el pipeline.") from exc

    step_errors: list[str] = []
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
            outs.anomalies.write_parquet(anom_path)
            outs.audit_log.write_parquet(audit_path)

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
        return 1

    logbook_path = write_logbook(run_root=run_paths.run_root, run_id=run_id.value)
    print(f"[ieo] Cuaderno de bitácora: {logbook_path}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ieo", description="Pipeline IEO (producción)")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Ejecuta pipeline sobre data/processed/perfiles_all.csv")
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


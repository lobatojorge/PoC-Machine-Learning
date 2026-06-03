"""
Paso 02 del pipeline: contrato + Isolation Forest por perfil, en paralelo.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ieo.observability.anomaly import IF_CONTAMINATION, IsolationForestConfig, detect_anomalies_isolation_forest
from ieo.validation.radial_contract import ViolationSeverity, validate_canonical_ctd_polars

ROW_ID_COL = "row_id"


@dataclass(frozen=True, slots=True)
class QcOneResult:
    ok: bool
    skipped: bool
    clean_path: str | None
    n_contract_errors: int
    has_contract_error: bool
    n_anomalies: int
    error: str | None


def effective_n_estimators(n_rows: int, *, cap: int = 200) -> int:
    """Menos árboles en perfiles pequeños (misma semilla y contamination)."""
    if n_rows <= 0:
        return 32
    # Perfil CTD típico: decenas–cientos de niveles; 200 árboles es redundante.
    scaled = max(48, min(cap, n_rows))
    return int(scaled)


def _outputs_paths(can_path: Path, run_data_dir: Path) -> tuple[Path, Path, Path]:
    stem = can_path.name.replace("ctd_canonical", "ctd_clean")
    clean = run_data_dir / stem
    anom = run_data_dir / can_path.name.replace("ctd_canonical", "ctd_anomalies")
    audit = run_data_dir / can_path.name.replace("ctd_canonical", "ctd_anomaly_audit")
    return clean, anom, audit


def qc_outputs_up_to_date(can_path: Path, run_data_dir: Path) -> bool:
    """True si clean/anomalies/audit existen y no son más viejos que el canónico."""
    clean, anom, audit = _outputs_paths(can_path, run_data_dir)
    if not (clean.is_file() and anom.is_file() and audit.is_file()):
        return False
    try:
        src_mtime = can_path.stat().st_mtime
        return (
            clean.stat().st_mtime >= src_mtime
            and anom.stat().st_mtime >= src_mtime
            and audit.stat().st_mtime >= src_mtime
        )
    except OSError:
        return False


def _qc_one_impl(
    can_path: Path,
    run_data_dir: Path,
    *,
    run_id: str,
    reuse: bool,
    if_cap: int,
    if_jobs: int,
) -> QcOneResult:
    import polars as pl

    clean_p, anom_p, audit_p = _outputs_paths(can_path, run_data_dir)

    if reuse and qc_outputs_up_to_date(can_path, run_data_dir):
        n_anom = 0
        try:
            n_anom = pl.scan_parquet(anom_p).select(pl.len()).collect().item()
        except Exception:
            pass
        n_contract = 0
        try:
            df = pl.read_parquet(can_path)
            cv = validate_canonical_ctd_polars(df)
            n_contract = sum(1 for v in cv if v.severity == ViolationSeverity.ERROR)
        except Exception:
            pass
        return QcOneResult(
            ok=True,
            skipped=True,
            clean_path=str(clean_p),
            n_contract_errors=n_contract,
            has_contract_error=n_contract > 0,
            n_anomalies=int(n_anom),
            error=None,
        )

    try:
        df_can = pl.read_parquet(can_path)
        if ROW_ID_COL not in df_can.columns:
            raise ValueError(f"Artefacto canónico sin `{ROW_ID_COL}`: {can_path.name}")

        cv = validate_canonical_ctd_polars(df_can)
        n_contract_err = sum(1 for v in cv if v.severity == ViolationSeverity.ERROR)

        n_rows = int(df_can.height)
        cfg = IsolationForestConfig(
            contamination=IF_CONTAMINATION,
            random_state=42,
            n_estimators=effective_n_estimators(n_rows, cap=if_cap),
        )
        outs = detect_anomalies_isolation_forest(
            df=df_can,
            row_id_col=ROW_ID_COL,
            config=cfg,
            run_id=run_id,
            source_file=can_path.name,
            n_jobs=if_jobs,
        )

        outs.clean.write_parquet(clean_p)
        outs.anomalies.write_parquet(anom_p)
        outs.audit_log.write_parquet(audit_p)

        return QcOneResult(
            ok=True,
            skipped=False,
            clean_path=str(clean_p),
            n_contract_errors=n_contract_err,
            has_contract_error=n_contract_err > 0,
            n_anomalies=len(outs.anomalies),
            error=None,
        )
    except Exception as exc:
        return QcOneResult(
            ok=False,
            skipped=False,
            clean_path=None,
            n_contract_errors=0,
            has_contract_error=False,
            n_anomalies=0,
            error=f"{can_path.name}: {type(exc).__name__}: {exc}",
        )


def _qc_worker(args: tuple[str, str, str, bool, int, int]) -> QcOneResult:
    can_s, data_dir_s, run_id, reuse, if_cap, if_jobs = args
    return _qc_one_impl(
        Path(can_s),
        Path(data_dir_s),
        run_id=run_id,
        reuse=reuse,
        if_cap=if_cap,
        if_jobs=if_jobs,
    )


def resolve_qc_workers(explicit: int | None = None) -> int:
    if explicit is not None and explicit > 0:
        return explicit
    raw = os.environ.get("IEO_QC_WORKERS", "").strip()
    if raw:
        try:
            n = int(raw)
            if n > 0:
                return n
        except ValueError:
            pass
    cpu = os.cpu_count() or 4
    return max(1, min(8, cpu - 1))


def run_qc_batch(
    *,
    canonical_paths: list[Path],
    run_data_dir: Path,
    run_id: str,
    on_progress: Callable[[int, int], None] | None = None,
    reuse: bool | None = None,
    workers: int | None = None,
    if_cap: int | None = None,
) -> tuple[list[Path], list[str], int, int, int, int]:
    """
    Procesa todos los canónicos. Devuelve
    (clean_paths, step_errors, n_contract_errors, n_anomalies, n_skipped, n_files_contract_err).
    """
    if reuse is None:
        reuse = os.environ.get("IEO_REUSE_QC", "1").strip().lower() not in ("0", "false", "no")

    cap = if_cap if if_cap is not None else _env_int_local("IEO_IF_N_ESTIMATORS", 200) or 200
    n_workers = resolve_qc_workers(workers)
    if_jobs = 1 if n_workers > 1 else -1

    clean_paths: list[Path] = []
    step_errors: list[str] = []
    n_contract = 0
    n_anomalies = 0
    n_skipped = 0
    n_files_contract_err = 0
    total = len(canonical_paths)
    done = 0

    task_args = [
        (str(p.resolve()), str(run_data_dir.resolve()), run_id, reuse, cap, if_jobs)
        for p in canonical_paths
    ]

    def _apply(r: QcOneResult) -> None:
        nonlocal n_contract, n_anomalies, n_skipped, n_files_contract_err
        if r.error:
            step_errors.append(r.error)
            return
        if r.clean_path:
            clean_paths.append(Path(r.clean_path))
        n_contract += r.n_contract_errors
        n_anomalies += r.n_anomalies
        if r.skipped:
            n_skipped += 1
        if r.has_contract_error:
            n_files_contract_err += 1

    if n_workers <= 1 or total <= 2:
        for args in task_args:
            _apply(_qc_worker(args))
            done += 1
            if on_progress:
                on_progress(done, total)
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(_qc_worker, a) for a in task_args]
            for fut in as_completed(futures):
                _apply(fut.result())
                done += 1
                if on_progress:
                    on_progress(done, total)

    return (
        clean_paths,
        step_errors,
        n_contract,
        n_anomalies,
        n_skipped,
        n_files_contract_err,
    )


def _env_int_local(name: str, default: int | None = None) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

#!/usr/bin/env python3
"""
Smoke end-to-end (terminal): pipeline → Parquet → QC como el visor → (opcional) Streamlit health.

Uso desde la raíz del repo:
  python scripts/e2e_smoke.py
  python scripts/e2e_smoke.py --skip-pipeline    # si ya hay corrida reciente
  python scripts/e2e_smoke.py --with-streamlit # arranca Streamlit ~15s y comprueba /_stcore/health

Salida: código 0 si todo OK; stderr del pipeline se imprime solo si falla.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "run"
SRC = ROOT / "src"
CSV = ROOT / "data" / "processed" / "perfiles_all.csv"


def _die(msg: str, code: int = 1) -> None:
    print(f"[e2e] FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _ok(msg: str) -> None:
    print(f"[e2e] OK: {msg}")


def run_pipeline() -> None:
    if not CSV.is_file():
        _die(f"Falta entrada del pipeline: {CSV}")
    main_py = RUN_DIR / "main.py"
    proc = subprocess.run(
        [sys.executable, str(main_py)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=7200,
    )
    if proc.returncode != 0:
        print(proc.stdout[-8000:] if proc.stdout else "", file=sys.stderr)
        print(proc.stderr[-8000:] if proc.stderr else "", file=sys.stderr)
        _die(f"pipeline exit code {proc.returncode}")
    # Avisos [ieo] en stderr no son fallo si exit 0
    _ok("python run/main.py terminó con código 0")


def load_latest_run() -> Path:
    sys.path.insert(0, str(RUN_DIR))
    from pipeline_runs import latest_valid_run_root, load_pipeline_viewer_data

    run_root = latest_valid_run_root(ROOT)
    if run_root is None:
        _die("No hay outputs/runs/<run_id>/data/perfiles_all.ctd_clean.parquet")
    pipe = load_pipeline_viewer_data(run_root)
    if pipe is None:
        _die(f"No se pudo cargar Parquet en {run_root}")
    _ok(
        f"Parquet limpio+anomalías · run_id={run_root.name} · "
        f"limpias={len(pipe.df_clean):,} anómalas={len(pipe.df_anomalies):,}"
    )
    return run_root


def simulate_viewer_contract(run_root: Path) -> None:
    """Misma lógica QC que run/app.py (T vía Polars + serie mensual)."""
    sys.path.insert(0, str(SRC))
    import numpy as np
    import pandas as pd
    import polars as pl
    from ieo.validation.radial_contract import (
        ViolationSeverity,
        format_violations_markdown,
        validate_canonical_ctd_polars,
        validate_monthly_radial_series,
    )

    sys.path.insert(0, str(RUN_DIR))
    from pipeline_runs import load_pipeline_viewer_data

    pipe = load_pipeline_viewer_data(run_root)
    if pipe is None:
        _die("load_pipeline_viewer_data devolvió None")

    df = pipe.df_clean
    chk = df[["fecha", "estacion", pipe.col_prof, pipe.col_temp]].copy()
    chk = chk.rename(columns={pipe.col_prof: "profundidad_m", pipe.col_temp: "temperatura_c"})
    if "cast" in df.columns:
        chk["cast"] = df["cast"]
    violations = list(validate_canonical_ctd_polars(pl.from_pandas(chk)))

    # Serie mensual mínima (una estación) como en app
    use_cols = ["fecha", pipe.col_prof, pipe.col_temp, "estacion"]
    if "cast" in df.columns:
        use_cols.append("cast")
    work = df[use_cols].copy()
    work["fecha"] = pd.to_datetime(work["fecha"], errors="coerce")
    work[pipe.col_prof] = pd.to_numeric(work[pipe.col_prof], errors="coerce")
    work[pipe.col_temp] = pd.to_numeric(work[pipe.col_temp], errors="coerce")
    work = work.dropna(subset=["fecha", pipe.col_prof, pipe.col_temp, "estacion"])
    if not work.empty and "cast" in work.columns:
        gk = ["cast", "estacion"]
    else:
        work["_fecha_d"] = work["fecha"].dt.date
        gk = ["_fecha_d", "estacion"]

    def interp_at_5(g: pd.DataFrame) -> float:
        dft = (
            pd.DataFrame({"z": g[pipe.col_prof], "v": g[pipe.col_temp]})
            .dropna()
            .groupby("z", as_index=False)["v"]
            .mean()
            .sort_values("z")
        )
        if dft.empty:
            return float("nan")
        z, v = dft["z"].to_numpy(float), dft["v"].to_numpy(float)
        if 5.0 < float(z[0]) or 5.0 > float(z[-1]):
            return float("nan")
        return float(np.interp(5.0, z, v))

    per_cast = (
        work.groupby(gk, as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "fecha": pd.to_datetime(g["fecha"].iloc[0]).to_period("M").to_timestamp(how="start"),
                    "valor_prof": interp_at_5(g),
                }
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    per_cast = per_cast.dropna(subset=["valor_prof", "fecha"])
    if not per_cast.empty:
        monthly = per_cast.groupby("estacion", as_index=False).agg({"fecha": "first", "valor_prof": "mean"})
        violations.extend(
            validate_monthly_radial_series(
                monthly,
                col_fecha="fecha",
                col_val="valor_prof",
                col_estacion="estacion",
                variable_kind="temperature",
            )
        )

    errs = [v for v in violations if v.severity == ViolationSeverity.ERROR]
    warns = [v for v in violations if v.severity == ViolationSeverity.WARNING]
    md = format_violations_markdown(warns + errs)
    if md:
        safe = md[:2000].encode("ascii", errors="replace").decode("ascii")
        print("[e2e] Contrato (resumen):\n" + safe)
    if errs:
        _die(f"{len(errs)} violación(es) ERROR en simulación visor")
    if warns:
        _ok(f"{len(warns)} WARNING(s) — el visor debe mostrar st.warning y seguir (no return)")
    else:
        _ok("sin WARNING ni ERROR en contrato simulado")


def streamlit_health_check(timeout_s: float = 45.0) -> None:
    app_py = RUN_DIR / "app.py"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_py),
            "--server.headless",
            "true",
            "--server.port",
            "8501",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(RUN_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = "http://127.0.0.1:8501/_stcore/health"
    deadline = time.time() + timeout_s
    last_err = ""
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                out = (proc.stdout.read() if proc.stdout else "") + (proc.stderr.read() if proc.stderr else "")
                _die(f"Streamlit terminó antes de health check:\n{out[-4000:]}")
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        _ok("Streamlit health 200 en :8501 (cierra el proceso manualmente si quedó en segundo plano)")
                        return
            except urllib.error.URLError as exc:
                last_err = str(exc)
            time.sleep(0.5)
        _die(f"Timeout esperando Streamlit ({last_err})")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    ap = argparse.ArgumentParser(description="E2E smoke IEO pipeline + visor")
    ap.add_argument("--skip-pipeline", action="store_true", help="No ejecutar run/main.py")
    ap.add_argument("--with-streamlit", action="store_true", help="Comprobar arranque HTTP de Streamlit")
    args = ap.parse_args()

    print(f"[e2e] Raíz: {ROOT}")
    if not args.skip_pipeline:
        run_pipeline()
    else:
        print("[e2e] --skip-pipeline: se asume corrida existente")

    run_root = load_latest_run()
    simulate_viewer_contract(run_root)

    if args.with_streamlit:
        streamlit_health_check()
    else:
        print(
            "[e2e] Siguiente paso manual: cd run && streamlit run app.py\n"
            "  (o: python scripts/e2e_smoke.py --with-streamlit para health check automático)"
        )

    print("[e2e] Smoke completado.")


if __name__ == "__main__":
    main()

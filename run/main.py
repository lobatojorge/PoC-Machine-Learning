from __future__ import annotations

"""
run/main.py — Orquestador del pipeline Sireno Gijón.
Ubicado en `run/` para mantener la raíz mínima.
"""

import subprocess
import sys
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent


def _run_step(script_relative_path: str) -> None:
    script_path = PROJECT_ROOT / script_relative_path
    cmd = [sys.executable, str(script_path)]
    print(f"\n[PIPELINE] Ejecutando: {script_relative_path}")
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if completed.returncode != 0:
        raise RuntimeError(
            f"Fallo en el paso '{script_relative_path}' con código {completed.returncode}."
        )


def main() -> None:
    steps = [
        "src/00_data_scout.py",
        "src/00_ingestion.py",
        "src/01_agent_inspector.py",
        "src/02_analysis.py",
    ]

    print("\n" + "=" * 80)
    print(" ORQUESTADOR SIRENO GIJÓN ".center(80, "="))
    print("=" * 80)
    print("Fuente esperada: data/raw/ExcelSirenoGijon.xls")
    print("-" * 80)

    for step in steps:
        _run_step(step)

    print("-" * 80)
    print("[OK] Pipeline completado.")
    print("Resultado principal: data/processed/sireno_gijon_ctd_processed.csv")
    print("Cuarentena ML:      data/quarantine/")
    print("Reporte de raw:     outputs/reports/recon_data_raw.txt")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()


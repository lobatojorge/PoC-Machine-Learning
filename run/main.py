from __future__ import annotations

"""
run/main.py — Orquestador del pipeline (producción).

La salida estructurada en consola (datos → pasos → progreso → resultados → Streamlit)
la genera ``ieo.cli.run_pipeline`` vía ``ieo.reports.console_run``.

Códigos de salida
-----------------
0 → completado (puede incluir avisos parciales en QC).
1 → error grave en ingesta o sin perfiles limpios.
2 → no se encontraron ficheros .cnv en data/cnv/.
3 → todos los ficheros rechazados en el control previo (cuarentena).
"""

import sys
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent


def main() -> None:
    src_dir = PROJECT_ROOT / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    try:
        from ieo.observability.session_audit import append_public_run_journal_entry  # noqa: E402

        append_public_run_journal_entry(
            PROJECT_ROOT,
            kind="pipeline_cli",
            extra={"nota": "python run/main.py"},
        )
    except Exception:
        pass

    from ieo.cli import run_pipeline  # noqa: E402

    raise SystemExit(int(run_pipeline(project_root=PROJECT_ROOT)))


if __name__ == "__main__":
    main()

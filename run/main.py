from __future__ import annotations

"""
run/main.py — Orquestador del pipeline (producción).

Nota práctica
-------------
Este archivo existe para que un usuario inexperto pueda ejecutar el pipeline
con un solo comando, pero la lógica real vive en `src/ieo/`.
"""

import sys
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent


def main() -> None:
    print("\n" + "=" * 80)
    print(" ORQUESTADOR (PRODUCCIÓN) ".center(80, "="))
    print("=" * 80)
    print("Entrada: `data/processed/perfiles_all.csv` (p. ej. generado desde raw con `python run/build_processed_from_raw.py`).")
    print("Nota: el CSV largo en `data/raw/` se materializa a processed con `python run/build_processed_from_raw.py`.")
    print("-" * 80)

    # Import diferido: permite ejecutar desde `run/` sin instalar paquete.
    # Este repo usa “src layout”, por eso añadimos `PROJECT_ROOT/src` al path.
    src_dir = PROJECT_ROOT / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    try:
        from ieo.observability.session_audit import append_public_run_journal_entry  # noqa: E402

        audit_path = append_public_run_journal_entry(
            PROJECT_ROOT,
            kind="pipeline_cli",
            extra={"nota": "Inicio de run/main.py; detalle en consola y en outputs/runs/<run_id>/"},
        )
        print(f"Registro de auditoría (apéndice): {audit_path}")
    except Exception as exc:
        print(f"[aviso] No se pudo escribir el registro de auditoría: {type(exc).__name__}: {exc}")

    from ieo.cli import run_pipeline  # noqa: E402
    exit_code = int(run_pipeline(project_root=PROJECT_ROOT))

    print("-" * 80)
    if exit_code == 0:
        print("[OK] Pipeline completado.")
        print("Revisa outputs/runs/<run_id>/ para datos y reportes.")
    else:
        print(f"[!!] Pipeline terminó con código: {exit_code}")
        print("Revisa outputs/runs/<run_id>/checkpoints/ para entender qué falló.")
    print("=" * 80 + "\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()


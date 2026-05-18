from __future__ import annotations

"""
run/main.py — Orquestador del pipeline (producción).

Nota práctica
-------------
Este archivo existe para que un usuario inexperto pueda ejecutar el pipeline
con un solo comando, pero la lógica real vive en `src/ieo/`.

Carpetas de entrada
-------------------
- data/cnv/  → ficheros .cnv (todas las radiales en disco; el pipeline solo ingiere Cudillero).

Tras cada ejecución de ``python run/main.py``
-----------------
- ``outputs/RESUMEN_ULTIMA.html`` → resumen visual único (se sobrescribe siempre).

Códigos de salida
-----------------
0 → todo bien.
1 → error en ingesta o anomalías (revisa checkpoints/).
2 → no se encontraron ficheros .cnv en data/cnv/ (ni subcarpetas).
3 → todos los ficheros rechazados por la puerta de cuarentena (ver data/quarantine/).
"""

import json
import sys
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent

_EXIT_MESSAGES = {
    0: "[OK] Pipeline completado sin errores.",
    1: "[!!] Pipeline con errores en ingesta o anomalías.",
    2: "[!!] No se encontraron ficheros .cnv en data/cnv/ (ni subcarpetas).",
    3: "[!!] Todos los ficheros rechazados por la puerta de cuarentena (ver data/quarantine/).",
}


def _print_run_summary(run_root: Path) -> None:
    """Lee run_summary.json (y provenance.json si existe) y muestra un resumen legible en consola."""
    summary_path = run_root / "run_summary.json"
    if not summary_path.exists():
        return
    try:
        s = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return

    print(f"  Run ID        : {s.get('run_id', '?')}")
    steps_ok = s.get("steps_ok", [])
    steps_fail = s.get("steps_failed", [])
    if steps_ok:
        print(f"  Pasos OK      : {', '.join(steps_ok)}")
    if steps_fail:
        print(f"  Pasos fallidos: {', '.join(steps_fail)}")
    ingest = s.get("ingest")
    if ingest:
        from ieo.reports.resumen_ultima import format_ingest_console  # noqa: PLC0415

        print(format_ingest_console(ingest))
    print(f"  Anomalías IF  : {s.get('n_anomalies', 0)}")
    print(f"  Errores QC    : {s.get('contract_errors', 0)}")
    quarantine = s.get("quarantine", [])
    if quarantine:
        print(f"  Cuarentena    : {', '.join(quarantine)}")
    artifacts = s.get("artifacts", {})
    if artifacts.get("clean_all"):
        print(f"  Parquet limpio (todos): {artifacts['clean_all']}")
    elif artifacts.get("clean"):
        print(f"  Parquet limpio: {artifacts['clean']}")
    print(f"  Generado UTC  : {s.get('generated_at_utc', '?')}")
    print(f"  Resumen JSON  : {summary_path}")

    # Mostrar hash SHA256 del fichero fuente desde provenance.json
    prov_path = run_root / "provenance.json"
    if prov_path.exists():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            for inp in prov.get("inputs", []):
                sha = inp.get("sha256")
                src = Path(inp.get("path", "")).name
                if sha:
                    print(f"  SHA256 ({src[:30]:<30}): {sha[:16]}…")
        except Exception:
            pass
        print(f"  Provenance    : {prov_path}")


def main() -> None:
    print("\n" + "=" * 80)
    print(" ORQUESTADOR (PRODUCCIÓN) ".center(80, "="))
    print("=" * 80)
    print("Entrada : data/cnv/**/*.cnv  (solo se procesa radial Cudillero; ver README)")
    print("-" * 80)

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
    print(_EXIT_MESSAGES.get(exit_code, f"[??] Código desconocido: {exit_code}"))

    # Mostrar run_summary.json de la ejecución más reciente
    runs_dir = PROJECT_ROOT / "outputs" / "runs"
    if runs_dir.exists():
        candidates = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir() and (d / "run_summary.json").exists()],
            key=lambda d: d.stat().st_mtime,
        )
        if candidates:
            print()
            _print_run_summary(candidates[-1])

    resumen_html = PROJECT_ROOT / "outputs" / "RESUMEN_ULTIMA.html"
    leeme = PROJECT_ROOT / "outputs" / "LEEME_RESUMEN.txt"
    if resumen_html.is_file():
        print(f"  Resumen visual : {resumen_html.resolve()}")
    elif leeme.is_file():
        print(f"  (HTML no generado; ver {leeme.resolve()})")
    else:
        print("  Resumen visual : no generado (ejecuta el pipeline con al menos un .cnv válido)")

    if exit_code != 0:
        print()
        print("Más detalle en: outputs/runs/<run_id>/checkpoints/ (informes HTML por paso)")
    print("=" * 80 + "\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Preflight de ``data/cnv/``: carpetas sin convención ``AAAA/``, puerta de ingesta y dudas.

Uso típico tras añadir lotes (p. ej. ``St.1 CNVs``)::

    python run/preflight_cnv.py

Opciones::

    python run/preflight_cnv.py --all          # todo el repo (lento)
    python run/preflight_cnv.py --interactive  # pausa entre preguntas (consola TTY)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent
_SRC = (PROJECT_ROOT / "src").resolve()
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ieo.cnv_preflight import (  # noqa: E402
    print_preflight_dialogue,
    run_cnv_preflight,
    write_preflight_json,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Preflight de .cnv bajo data/cnv/")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Analizar todos los .cnv (por defecto solo carpetas cuyo nombre no es AAAA).",
    )
    ap.add_argument(
        "--interactive",
        action="store_true",
        help="Tras cada pregunta sugerida, esperar Enter (solo tiene sentido en consola interactiva).",
    )
    ap.add_argument(
        "--json-out",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "temporal" / "cnv_preflight_report.json",
        help="Ruta del informe JSON (detalle por fichero si no se usa --compact-json).",
    )
    ap.add_argument(
        "--compact-json",
        action="store_true",
        help="Excluir la lista completa «rows» del JSON (solo agregados y dubios).",
    )
    args = ap.parse_args()

    mode = "all" if args.all else "non_year_shards"
    report = run_cnv_preflight(
        PROJECT_ROOT,
        mode=mode,
        include_per_file_rows=not args.compact_json,
    )

    if args.interactive and sys.stdin.isatty():
        print("=== Modo interactivo ===\n")
        for i, q in enumerate(report.get("questions") or [], start=1):
            print(f"Pregunta {i}:\n  {q}\n")
            input("Pulse Enter para continuar… ")
        print()

    print_preflight_dialogue(report)
    write_preflight_json(report, args.json_out.resolve())
    print(f"\n[ok] Informe JSON: {args.json_out.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

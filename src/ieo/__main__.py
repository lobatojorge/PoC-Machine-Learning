"""
Permite: python -m ieo run --project-root .
(con `src` en PYTHONPATH, p. ej. desde la raíz del repo).
"""

from __future__ import annotations

from ieo.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

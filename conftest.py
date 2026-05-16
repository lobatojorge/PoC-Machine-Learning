"""Configuración pytest: añade src/ y run/ al sys.path.

Necesario para que los tests importen `ieo.*` (desde src/) y
`pipeline_runs` (desde run/) sin necesidad de instalar el paquete.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "run"))

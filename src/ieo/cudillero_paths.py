"""
Rutas de datos para el pipeline Cudillero.

Carpetas de entrada
-------------------
- ``data/cnv/``   : repositorio de ficheros .cnv del técnico (pueden incluir **todas**
  las radiales: Gijón, Santander, Vigo, …). El pipeline filtra y solo ingiere **Cudillero**
  (véase ``ieo/io/cnv_radial.py``).

Carpeta de salida interna
--------------------------
- ``data/checked/`` : ficheros verificados (opcional; no es la entrada del pipeline).
"""

from __future__ import annotations

from pathlib import Path


def cnv_dir(project_root: Path) -> Path:
    """Carpeta donde el técnico deposita los ficheros .cnv (todas las radiales en disco)."""
    return (project_root / "data" / "cnv").resolve()


def csv_dir(project_root: Path) -> Path:
    """Carpeta de CSV de demo (legacy)."""
    return (project_root / "data" / "csv").resolve()


def checked_dir(project_root: Path) -> Path:
    """Carpeta de ficheros verificados (destino opcional)."""
    return (project_root / "data" / "checked").resolve()


def default_radial_csv_path(project_root: Path) -> Path:
    """Ruta heredada del flujo CSV."""
    return (project_root / "data" / "checked" / "perfiles_all.csv").resolve()

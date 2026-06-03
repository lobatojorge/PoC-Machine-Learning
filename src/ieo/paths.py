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

import re
from pathlib import Path

_YEAR_DIR = re.compile(r"^\d{4}$")


def cnv_dir(project_root: Path) -> Path:
    """Carpeta donde el técnico deposita los ficheros .cnv (todas las radiales en disco)."""
    return (project_root / "data" / "cnv").resolve()


def cnv_file_label_under_root(cnv_root: Path, path: Path) -> str:
    """
    Etiqueta corta para logs y cuarentena: ``AAAA/nombre.cnv`` si el primer segmento
    relativo a ``cnv_root`` es un año (4 dígitos); si no, ``subcarpeta/.../nombre`` o solo el nombre.
    """
    try:
        rel = path.resolve().relative_to(cnv_root.resolve())
    except ValueError:
        return path.name
    parts = rel.parts
    if len(parts) >= 2 and _YEAR_DIR.match(parts[0]):
        return f"{parts[0]}/{parts[-1]}"
    if len(parts) > 1:
        return rel.as_posix()
    return parts[-1]


def csv_dir(project_root: Path) -> Path:
    """Carpeta de CSV de demo (legacy)."""
    return (project_root / "data" / "csv").resolve()


def checked_dir(project_root: Path) -> Path:
    """Carpeta de ficheros verificados (destino opcional)."""
    return (project_root / "data" / "checked").resolve()


def default_radial_csv_path(project_root: Path) -> Path:
    """Ruta heredada del flujo CSV."""
    return (project_root / "data" / "checked" / "perfiles_all.csv").resolve()


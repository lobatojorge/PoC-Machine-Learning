"""Rutas del CSV radial Cudillero (solo stdlib; usable desde pipeline sin arrastrar lectores)."""

from __future__ import annotations

from pathlib import Path


def default_radial_csv_path(project_root: Path) -> Path:
    """CSV radial canónico: ``data/processed/perfiles_all.csv``."""
    return (project_root / "data" / "processed" / "perfiles_all.csv").resolve()

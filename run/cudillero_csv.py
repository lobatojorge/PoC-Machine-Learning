"""Carga `default_radial_csv_path` sin `import ieo.*` (colisión con paquete pip homónimo en Streamlit)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MOD_NAME = "_ieo_repo_cudillero_paths"


def _cudillero_paths_mod():
    if _MOD_NAME in sys.modules:
        return sys.modules[_MOD_NAME]
    here = Path(__file__).resolve().parent
    src_path = here.parent / "src" / "ieo" / "cudillero_paths.py"
    spec = importlib.util.spec_from_file_location(_MOD_NAME, src_path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"No se encuentra {src_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def default_radial_csv_path(project_root: Path) -> Path:
    return _cudillero_paths_mod().default_radial_csv_path(project_root)

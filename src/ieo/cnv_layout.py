"""
Clasificación superficial de rutas bajo ``data/cnv/``.

Sirve para detectar lotes con nomenclatura distinta a ``AAAA/`` (p. ej. ``St.1 CNVs``)
sin abrir cada fichero.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

_YEAR_SEGMENT = re.compile(r"^\d{4}$")


def first_segment_under_cnv_root(cnv_root: Path, path: Path) -> str | None:
    """Primer componente de la ruta relativa a ``cnv_root``, o ``None`` si no aplica."""
    try:
        rel = path.resolve().relative_to(cnv_root.resolve())
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def is_year_shard_segment(segment: str) -> bool:
    """True si el segmento es solo cuatro dígitos (convención carpeta-año)."""
    return bool(_YEAR_SEGMENT.match(segment))


def is_non_year_shard_under_cnv(cnv_root: Path, path: Path) -> bool:
    """True si el fichero está bajo una subcarpeta cuyo nombre no es ``YYYY``."""
    seg = first_segment_under_cnv_root(cnv_root, path)
    if seg is None:
        return False
    return not is_year_shard_segment(seg)


def cnv_data_tree_fingerprint(cnv_root: Path) -> str:
    """
    Huella barata del árbol ``*.cnv`` bajo ``cnv_root``: número de ficheros + ``mtime_ns`` máximo.

    Sirve para invalidar cachés (p. ej. índice geo del visor) sin reabrir cabeceras.
    """
    if not cnv_root.is_dir():
        return "missing"
    paths = sorted(cnv_root.rglob("*.cnv"))
    if not paths:
        return "empty"
    max_ns = 0
    for p in paths:
        try:
            max_ns = max(max_ns, p.stat().st_mtime_ns)
        except OSError:
            continue
    return f"{len(paths)}:{max_ns}"


def non_year_shard_counts(cnv_root: Path, paths: list[Path]) -> dict[str, int]:
    """Conteos por primer segmento de ruta para ficheros fuera de carpetas ``YYYY``."""
    c: Counter[str] = Counter()
    for p in paths:
        if not is_non_year_shard_under_cnv(cnv_root, p):
            continue
        seg = first_segment_under_cnv_root(cnv_root, p)
        if seg:
            c[seg] += 1
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))

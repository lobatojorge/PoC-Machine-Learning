"""
Catálogo de códigos de estación por radial (sufijos en acrónimo / cast).

Uso temprano en ingesta o en el visor para no mezclar radiales en un mismo producto.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

# Identificadores internos estables (minúsculas, sin espacios).
RADIAL_ID_VIGO: Final = "vigo"
RADIAL_ID_CORUNA: Final = "coruna"
RADIAL_ID_CUDILLERO: Final = "cudillero"
RADIAL_ID_GIJON: Final = "gijon"
RADIAL_ID_SANTANDER: Final = "santander"

RADIAL_STATION_CODES: dict[str, tuple[str, ...]] = {
    RADIAL_ID_VIGO: ("E15VI", "E1VI", "E3VI"),
    RADIAL_ID_CORUNA: ("EPCO", "E4CO", "E3BCO", "E3CCO", "E3ACO", "E2TCO", "E2CO", "I1CO"),
    RADIAL_ID_CUDILLERO: ("E1CU", "E2CU", "E3CU"),
    RADIAL_ID_GIJON: ("E1GI", "E2GI", "E3GI", "E4GI"),
    RADIAL_ID_SANTANDER: ("E2SA", "E3SA", "E4SA", "E5SA", "E6SA", "E7SA", "E8SA", "AGL"),
}

_CODE_INDEX: list[tuple[str, str]] | None = None


def _build_code_index() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for radial_id, codes in RADIAL_STATION_CODES.items():
        for code in codes:
            pairs.append((code.upper(), radial_id))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def _code_index() -> list[tuple[str, str]]:
    global _CODE_INDEX
    if _CODE_INDEX is None:
        _CODE_INDEX = _build_code_index()
    return _CODE_INDEX


def identify_radial(text: str | None) -> str | None:
    """Infiere la radial a partir de un acrónimo, cast o nombre de fichero."""
    if text is None:
        return None
    upper = str(text).strip().upper()
    if not upper:
        return None
    for code, radial_id in _code_index():
        if code in upper:
            return radial_id
    return None


def attach_radial_id(df: pd.DataFrame, *, hint_columns: tuple[str, ...] = ("acronimo", "cast")) -> pd.DataFrame:
    """Añade columna ``radial_id`` si no existe, usando la primera columna de pista disponible."""
    if "radial_id" in df.columns:
        return df
    out = df.copy()
    for col in hint_columns:
        if col in out.columns:
            out["radial_id"] = out[col].map(lambda v: identify_radial(None if pd.isna(v) else str(v)))
            return out
    out["radial_id"] = pd.NA
    return out


def filter_dataframe_to_radial(df: pd.DataFrame, radial_id: str) -> tuple[pd.DataFrame, int]:
    """
    Filtra filas a una radial; devuelve (dataframe, filas descartadas).

    CSV legacy Cudillero: ``estacion`` 1–3 ↔ E1CU/E2CU/E3CU.

    Ficheros SeaBird ``.cnv`` (pipeline actual): la ingesta ya es solo Cudillero y
    ``** Station:`` suele ser 4–8, no 1–3. Si no hay ``radial_id`` inferible y ninguna
    fila cae en 1–3, se conservan todas las filas del Parquet (ya filtrado en paso 00a).
    """
    work = attach_radial_id(df)
    before = len(work)
    if work["radial_id"].notna().any():
        out = work[work["radial_id"] == radial_id].copy()
        return out, before - len(out)
    if radial_id == RADIAL_ID_CUDILLERO and "estacion" in work.columns:
        # Sin radial_id en datos: ingesta .cnv ya limitada a Cudillero; no recortar a 1–3.
        return work.copy(), 0
    return work.iloc[0:0].copy(), before

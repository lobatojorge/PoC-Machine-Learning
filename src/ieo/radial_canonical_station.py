"""Canonical transect station index (1..N) vs SeaBird Station metadata."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ieo.io.cnv_header import parse_station_from_folder_name
from ieo.radiales_catalog import RADIAL_ID_CUDILLERO, RADIAL_ID_GIJON, RADIAL_STATION_CODES, identify_radial

CANONICAL_STATION_COL = "estacion_canonica"


def _station_index_from_code(radial_id: str, text: str | None) -> int | None:
    if not text or not str(text).strip():
        return None
    upper = str(text).upper()
    codes = RADIAL_STATION_CODES.get(radial_id, ())
    for idx, code in enumerate(codes, start=1):
        if code.upper() in upper:
            return idx
    rid = identify_radial(upper)
    if rid != radial_id:
        return None
    return None


def resolve_canonical_station(
    radial_id: str,
    *,
    cast: str | None = None,
    acronimo: str | None = None,
    source_file: str | None = None,
    station_sbe: int | None = None,
    station_folder: int | None = None,
    cruise: str | None = None,
) -> int | None:
    """Return canonical station 1..N or None."""
    for hint in (cast, acronimo, source_file, cruise):
        idx = _station_index_from_code(radial_id, hint)
        if idx is not None:
            return idx

    if radial_id == RADIAL_ID_CUDILLERO and station_folder is not None:
        sf = int(station_folder)
        if 1 <= sf <= len(RADIAL_STATION_CODES.get(RADIAL_ID_CUDILLERO, ())):
            return sf

    if station_sbe is not None and int(station_sbe) != 0:
        sb = int(station_sbe)
        n_codes = len(RADIAL_STATION_CODES.get(radial_id, ()))
        if n_codes and 1 <= sb <= n_codes:
            return sb

    return None


def station_folder_from_path(path: Path | str | None) -> int | None:
    if path is None:
        return None
    return parse_station_from_folder_name(Path(path))


def apply_canonical_station_column(
    df: pd.DataFrame,
    radial_id: str,
    *,
    col_estacion: str = "estacion",
    overwrite: bool = False,
) -> pd.DataFrame:
    """Add estacion_canonica; optionally overwrite estacion for UI."""
    if df.empty:
        out = df.copy()
        out[CANONICAL_STATION_COL] = pd.Series(dtype="Int64")
        return out

    out = df.copy()

    def _row_canon(row: pd.Series) -> int | None:
        sf: int | None = None
        if "source_file" in row.index and pd.notna(row.get("source_file")):
            sf = station_folder_from_path(str(row["source_file"]))
        sbe = None
        if col_estacion in row.index and pd.notna(row.get(col_estacion)):
            try:
                sbe = int(float(row[col_estacion]))
            except (TypeError, ValueError):
                sbe = None
        return resolve_canonical_station(
            radial_id,
            cast=str(row["cast"]) if "cast" in row.index and pd.notna(row.get("cast")) else None,
            acronimo=str(row["acronimo"]) if "acronimo" in row.index and pd.notna(row.get("acronimo")) else None,
            source_file=str(row["source_file"]) if "source_file" in row.index and pd.notna(row.get("source_file")) else None,
            station_sbe=sbe,
            station_folder=sf,
        )

    out[CANONICAL_STATION_COL] = out.apply(_row_canon, axis=1)
    if overwrite:
        mapped = out[CANONICAL_STATION_COL].notna()
        out.loc[mapped, col_estacion] = out.loc[mapped, CANONICAL_STATION_COL].astype(int)
    return out


def canonical_station_options(
    df: pd.DataFrame,
    radial_id: str,
    *,
    col_estacion: str = "estacion",
) -> list[int]:
    """Sorted canonical station ids present in df."""
    col = CANONICAL_STATION_COL if CANONICAL_STATION_COL in df.columns else col_estacion
    if col not in df.columns:
        return []
    vals = df[col].dropna().unique()
    opts = sorted({int(float(x)) for x in vals})
    n_max = len(RADIAL_STATION_CODES.get(radial_id, ()))
    if n_max:
        opts = [o for o in opts if 1 <= o <= n_max]
    if radial_id == RADIAL_ID_GIJON:
        opts = [o for o in opts if o != 0]
    return opts


def station_display_name(radial_id: str, station_idx: int) -> str:
    codes = RADIAL_STATION_CODES.get(radial_id, ())
    if 1 <= station_idx <= len(codes):
        return str(codes[station_idx - 1])
    return f"Estacion {station_idx}"

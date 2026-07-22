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
    codes = RADIAL_STATION_CODES.get(radial_id, ())
    # Build a fast upper-case code → 1-based index map
    _upper_map: dict[str, int] = {c.upper(): i for i, c in enumerate(codes, start=1)}

    def _canon_from_series(s: pd.Series) -> pd.Series:
        """Vectorized: first code match in upper-cased text wins."""
        def _match(text: object) -> int | None:
            if text is None or (isinstance(text, float) and pd.isna(text)):
                return None
            upper = str(text).upper()
            for code, idx in _upper_map.items():
                if code in upper:
                    return idx
            return None
        return s.map(_match)

    # Try hint columns in priority order — stop at the first that yields any match
    for hint_col in ("cast", "acronimo", "source_file"):
        if hint_col in out.columns:
            result = _canon_from_series(out[hint_col])
            if result.notna().any():
                out[CANONICAL_STATION_COL] = result
                break
    else:
        # Fall back to SBE station number if it falls within valid range
        if col_estacion in out.columns and len(codes) > 0:
            def _sbe_match(v: object) -> int | None:
                try:
                    sb = int(float(v))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return None
                return sb if 1 <= sb <= len(codes) else None
            out[CANONICAL_STATION_COL] = out[col_estacion].map(_sbe_match)
        else:
            out[CANONICAL_STATION_COL] = pd.NA

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

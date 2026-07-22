"""
Carga ligera de perfiles CTD desde ``.cnv`` para una radial (sin pipeline completo).

Pensado para visualizaciones exploratorias (p. ej. series temporales de Gijón)
leyendo solo ficheros con temperatura en cabecera.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import polars as pl

from ieo.paths import cnv_dir
from ieo.io.cnv_header import (
    parse_cnv_column_names_from_path,
    parse_cnv_station_number_from_path,
    parse_station_from_folder_name,
    parse_station_from_filename,
)
from ieo.io.cnv_radial import classify_cnv_radial, filter_paths_by_radial
from ieo.io.cnv_reader import CnvReader
from ieo.transform.canonical_schema import (
    CTDCanonicalSchema,
    normalize_ctd_columns,
    resolve_depth_source_column,
)
from ieo.validation.radial_contract import filter_sampling_dates_pandas

_TEMP_HEADER_COLS = frozenset(
    {"t090c", "t068", "temperatura_c", "temp", "temperature", "t190c"},
)


def header_has_ctd_temperature(source: Path) -> bool:
    names = parse_cnv_column_names_from_path(source)
    if not names:
        return False
    return bool(_TEMP_HEADER_COLS & {n.lower() for n in names})


def _resolve_station_number(path: Path, pdf: pd.DataFrame) -> pd.DataFrame:
    """
    Populates 'estacion' from fallback parsers when not already present in the frame.
    Single responsibility: station metadata enrichment only.
    """
    if "estacion" in pdf.columns:
        return pdf
    stn = parse_cnv_station_number_from_path(path)
    if stn is None:
        stn = parse_station_from_folder_name(path)
    if stn is None:
        stn = parse_station_from_filename(path)
    pdf["estacion"] = int(stn) if stn is not None else pd.NA
    return pdf


def _read_single_cnv_to_pandas(
    path: Path,
    *,
    reader: CnvReader,
    schema: CTDCanonicalSchema,
    staging: Path,
) -> pd.DataFrame | None:
    """
    Reads one .cnv file to a canonical Pandas DataFrame.
    Returns None if the file has no temperature column.
    Single responsibility: one-file I/O + schema normalisation only.
    Raises: OSError, ValueError, polars.exceptions.ComputeError
    """
    if not header_has_ctd_temperature(path):
        return None
    res = reader.read(path, staging_dir=staging)
    lf = normalize_ctd_columns(res.lazyframe, schema=schema)
    frame = lf.collect()
    if "profundidad_m" not in frame.columns:
        _depth_src = resolve_depth_source_column(frame.columns)
        if _depth_src:
            frame = frame.with_columns(
                pl.col(_depth_src).cast(pl.Float64, strict=False).alias("profundidad_m")
            )
        else:
            frame = frame.with_columns(
                pl.lit(None, dtype=pl.Float64).alias("profundidad_m")
            )
    return frame.to_pandas()


def load_radial_profiles_pandas(
    project_root: Path,
    radial_id: str,
    *,
    max_files: int | None = None,
    station_number: int | None = None,
) -> tuple[pd.DataFrame, dict[str, int | str]]:
    """
    Lee ficheros ``.cnv`` de ``data/cnv/`` para ``radial_id`` y devuelve un DataFrame pandas canónico.

    Omite ficheros sin columna de temperatura (p. ej. solo PAR) y los que fallen al parsear.
    """
    root = project_root.resolve()
    all_cnv = sorted(cnv_dir(root).rglob("*.cnv"))
    radial_paths, _, omitidas = filter_paths_by_radial(all_cnv, radial_id, cnv_root=cnv_dir(root))

    stats: dict[str, int | str] = {
        "radial_id": radial_id,
        "n_cnv_total": len(all_cnv),
        "n_radial_clasificados": len(radial_paths),
        "omitidas_por_radial": omitidas,
    }

    if station_number is not None:
        radial_paths = [
            p
            for p in radial_paths
            if parse_cnv_station_number_from_path(p) == int(station_number)
        ]
        stats["station_sbe"] = int(station_number)
        stats["n_tras_filtro_estacion"] = len(radial_paths)

    if max_files is not None and max_files > 0:
        radial_paths = radial_paths[: int(max_files)]

    staging = root / "outputs" / "staging_radial_viz"
    staging.mkdir(parents=True, exist_ok=True)
    reader = CnvReader()
    schema = CTDCanonicalSchema()

    frames: list[pd.DataFrame] = []
    n_skip_no_temp = 0
    n_errors = 0

    for path in radial_paths:
        if classify_cnv_radial(path) != radial_id:
            continue
        try:
            pdf = _read_single_cnv_to_pandas(path, reader=reader, schema=schema, staging=staging)
            if pdf is None:
                n_skip_no_temp += 1
                continue
            pdf = _resolve_station_number(path, pdf)
            pdf["source_file"] = path.name
            frames.append(pdf)
        except (OSError, ValueError, pl.exceptions.ComputeError):
            n_errors += 1

    stats["n_con_temperatura_intentados"] = len(radial_paths) - n_skip_no_temp
    stats["n_omitidos_sin_temperatura"] = n_skip_no_temp
    stats["n_errores_lectura"] = n_errors
    stats["n_perfiles_cargados"] = len(frames)

    if not frames:
        return pd.DataFrame(), stats

    out = pd.concat(frames, ignore_index=True)
    from ieo.radial_canonical_station import apply_canonical_station_column  # noqa: PLC0415

    out = apply_canonical_station_column(out, radial_id, overwrite=True)
    out, n_drop_dates = filter_sampling_dates_pandas(out, col_fecha="fecha")
    if n_drop_dates:
        stats["n_filas_fecha_fuera_rango"] = n_drop_dates
    stats["n_filas"] = int(len(out))
    if "fecha" in out.columns:
        fc = pd.to_datetime(out["fecha"], errors="coerce").dropna()
        if len(fc):
            stats["fecha_min"] = str(fc.min().date())
            stats["fecha_max"] = str(fc.max().date())
    return out, stats


def max_files_from_env() -> int | None:
    raw = os.environ.get("IEO_MAX_CNV", "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except ValueError:
        return None

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import polars as pl

# Profundidad en metros antes que presión (``prSE`` en psi no es profundidad).
_DEPTH_SOURCE_CANDIDATES: tuple[str, ...] = (
    "profundidad_m",
    "profundidad",
    "depth",
    "deps",
    "depsm",
    "dep_sm",
    "dep_sm [m]",
    "dep",
    "prdm",
    "prdm [m]",
    "prsm",
    "prsm [db]",
    "press",
    "pr",
    "prse",
)


@dataclass(frozen=True, slots=True)
class CTDCanonicalSchema:
    """
    Esquema canónico CTD (mínimo viable para el pipeline).

    Explicación práctica
    --------------------
    Distintos ficheros traen nombres diferentes (p.ej. `temp`, `t090C`, `temperature`).
    Aquí definimos *una sola forma* para el proyecto, para que los pasos siguientes
    no dependan del formato original.
    """

    # Identidad / claves
    run_id: str = "run_id"
    source_file: str = "source_file"
    row_id: str = "row_id"

    # Tiempo / muestreo
    fecha: str = "fecha"  # Datetime (UTC si se conoce)
    estacion: str = "estacion"
    cast: str = "cast"

    # Variables oceanográficas base
    profundidad_m: str = "profundidad_m"
    temperatura_c: str = "temperatura_c"
    salinidad_psu: str = "salinidad_psu"

    def required_columns(self) -> list[str]:
        return [
            self.fecha,
            self.estacion,
            self.cast,
            self.profundidad_m,
            self.temperatura_c,
        ]


def _first_present(candidates: Iterable[str], columns: list[str]) -> str | None:
    cols = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    return None


def resolve_depth_source_column(columns: list[str]) -> str | None:
    """Nombre real de la columna de profundidad/presión en un CTD SBE, si existe."""
    return _first_present(_DEPTH_SOURCE_CANDIDATES, columns)


def ensure_profundidad_m_pandas(df: pd.DataFrame, *, col_out: str = "profundidad_m") -> pd.DataFrame:
    """Garantiza ``profundidad_m`` copiando desde ``deps`` / ``pr`` / similares cuando falta."""
    if col_out in df.columns:
        return df
    src = resolve_depth_source_column([str(c) for c in df.columns])
    out = df.copy()
    if src is not None:
        out[col_out] = pd.to_numeric(out[src], errors="coerce")
    else:
        out[col_out] = pd.NA
    return out


def normalize_ctd_columns(lf: pl.LazyFrame, *, schema: CTDCanonicalSchema) -> pl.LazyFrame:
    """
    Normaliza nombres y tipos a un CTD canónico.

    Nota práctica:
    - Si falta una columna crítica, el pipeline fallará con un reporte claro.
    """

    cols = lf.collect_schema().names()

    # Profundidad / presión (``depS`` en cabecera → ``deps`` en datos)
    col_z = resolve_depth_source_column(cols)
    # Temperatura
    col_t = _first_present(
        [
            "temperatura_c",
            "temperatura",
            "temp",
            "temperature",
            "t090c",
            "t068",
            "t068c",
            "tv290c",
            "ts068",
            "potemp068",
            "potemp068c",
        ],
        cols,
    )
    # Salinidad (opcional)
    col_s = _first_present(
        ["salinidad_psu", "salinidad", "salinity", "sal", "sal00"],
        cols,
    )

    # Tiempo calendario (no mapear ``timeJ`` / ``time`` SBE: son días o segundos, no fechas ISO)
    col_fecha = _first_present(
        ["fecha", "date", "datetime", "timestamp"],
        cols,
    )
    # Estación / cast
    col_est = _first_present(["estacion", "station", "est"], cols)
    col_cast = _first_present(["cast"], cols)

    exprs: list[pl.Expr] = []
    if col_fecha is not None:
        exprs.append(pl.col(col_fecha).cast(pl.Datetime, strict=False).alias(schema.fecha))
    if col_est is not None:
        exprs.append(pl.col(col_est).cast(pl.Utf8, strict=False).alias(schema.estacion))
    if col_cast is not None:
        exprs.append(pl.col(col_cast).cast(pl.Utf8, strict=False).alias(schema.cast))

    if col_z is not None:
        exprs.append(pl.col(col_z).cast(pl.Float64, strict=False).alias(schema.profundidad_m))
    else:
        exprs.append(pl.lit(None, dtype=pl.Float64).alias(schema.profundidad_m))
    if col_t is not None:
        exprs.append(pl.col(col_t).cast(pl.Float64, strict=False).alias(schema.temperatura_c))
    else:
        exprs.append(pl.lit(None, dtype=pl.Float64).alias(schema.temperatura_c))
    if col_s is not None:
        exprs.append(pl.col(col_s).cast(pl.Float64, strict=False).alias(schema.salinidad_psu))
    else:
        exprs.append(pl.lit(None, dtype=pl.Float64).alias(schema.salinidad_psu))

    # Mantener el resto de columnas (como “extras”) por si ayudan al análisis posterior.
    keep = [c for c in cols if c not in {col_fecha, col_est, col_cast, col_z, col_t, col_s}]
    out = lf.select([*exprs, *[pl.col(c) for c in keep]])

    if col_z is not None and col_t is not None:
        out = out.filter(
            pl.col(schema.profundidad_m).is_not_null() & pl.col(schema.temperatura_c).is_not_null()
        )

    # Red de seguridad: versiones antiguas del normalizador podían omitir el alias.
    if schema.profundidad_m not in out.collect_schema().names():
        if col_z is not None:
            out = out.with_columns(
                pl.col(col_z).cast(pl.Float64, strict=False).alias(schema.profundidad_m)
            )
        else:
            out = out.with_columns(pl.lit(None, dtype=pl.Float64).alias(schema.profundidad_m))

    if schema.fecha in out.collect_schema().names():
        from ieo.validation.radial_contract import default_thresholds_from_env  # noqa: PLC0415

        th = default_thresholds_from_env()
        fcol = pl.col(schema.fecha)
        out = out.filter(
            fcol.is_null()
            | (
                fcol.dt.year().is_between(th.sampling_year_min, th.sampling_year_max, closed="both")
            )
        )
    return out


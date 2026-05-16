from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import polars as pl


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


def normalize_ctd_columns(lf: pl.LazyFrame, *, schema: CTDCanonicalSchema) -> pl.LazyFrame:
    """
    Normaliza nombres y tipos a un CTD canónico.

    Nota práctica:
    - Si falta una columna crítica, el pipeline fallará con un reporte claro.
    """

    cols = lf.collect_schema().names()

    # Profundidad
    col_z = _first_present(
        ["profundidad_m", "profundidad", "depth", "dep", "press", "depsm", "dep_sm", "dep_sm [m]", "prdm", "prdm [m]"],
        cols,
    )
    # Temperatura
    col_t = _first_present(
        [
            "temperatura_c",
            "temperatura",
            "temp",
            "temperature",
            "t090c",
            "t068",
            "tv290c",
        ],
        cols,
    )
    # Salinidad (opcional)
    col_s = _first_present(
        ["salinidad_psu", "salinidad", "salinity", "sal", "sal00"],
        cols,
    )

    # Tiempo
    col_fecha = _first_present(
        ["fecha", "date", "datetime", "time", "timejv2", "time_j", "timej", "time_s", "timestamp"],
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
    if col_t is not None:
        exprs.append(pl.col(col_t).cast(pl.Float64, strict=False).alias(schema.temperatura_c))
    if col_s is not None:
        exprs.append(pl.col(col_s).cast(pl.Float64, strict=False).alias(schema.salinidad_psu))
    else:
        exprs.append(pl.lit(None, dtype=pl.Float64).alias(schema.salinidad_psu))

    # Mantener el resto de columnas (como “extras”) por si ayudan al análisis posterior.
    keep = [c for c in cols if c not in {col_fecha, col_est, col_cast, col_z, col_t, col_s}]
    out = lf.select([*exprs, *[pl.col(c) for c in keep]])

    # Limpieza mínima (filas sin profundidad o temperatura no sirven)
    out = out.filter(pl.col(schema.profundidad_m).is_not_null() & pl.col(schema.temperatura_c).is_not_null())
    return out


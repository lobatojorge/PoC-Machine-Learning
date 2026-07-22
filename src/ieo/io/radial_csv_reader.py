"""CSV radial (perfiles en formato largo) → LazyFrame antes de ``normalize_ctd_columns``."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from ieo.paths import default_radial_csv_path  # reexport API estable
from ieo.io.base import ReadResult
from ieo.radiales_catalog import identify_radial


def _normalize_col_name(col: str) -> str:
    """Normaliza nombres de columna con tolerancia a BOM y comillas."""
    c = str(col).strip().lstrip("\ufeff").lower()
    # Headers tipo: "file","perfil",... pueden arrastrar comillas.
    c = c.strip('"').strip("'").strip()
    return c


def _lower_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    cur = lf.collect_schema().names()
    ren = {c: _normalize_col_name(c) for c in cur}
    return lf.rename(ren)


def _ensure_fecha(lf: pl.LazyFrame) -> pl.LazyFrame:
    cols = lf.collect_schema().names()
    if "fecha" in cols:
        return lf.with_columns(pl.col("fecha").cast(pl.Datetime, strict=False).alias("fecha"))
    if "anio" in cols or "año" in cols:
        yc = "anio" if "anio" in cols else "año"
        if "mes" in cols:
            return lf.with_columns(
                pl.datetime(
                    pl.col(yc).cast(pl.Int32, strict=False),
                    pl.col("mes").cast(pl.Int32, strict=False),
                    pl.lit(15).cast(pl.Int32),
                ).alias("fecha")
            )
        return lf.with_columns(
            pl.datetime(pl.col(yc).cast(pl.Int32, strict=False), pl.lit(6), pl.lit(15)).alias("fecha")
        )
    for c in cols:
        try:
            first = lf.select(pl.col(c).str.extract(r"((?:19|20)\d{2})", 1).first()).collect().item()
        except (pl.exceptions.PolarsError, pl.exceptions.InvalidOperationError, TypeError):
            first = None
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "radial_csv_reader: unexpected error probing column %r for year: %s", c, exc
            )
            first = None
        if first is not None and str(first).strip() != "":
            return lf.with_columns(
                pl.datetime(
                    pl.col(c).str.extract(r"((?:19|20)\d{2})", 1).cast(pl.Int32, strict=False),
                    pl.lit(6),
                    pl.lit(15),
                ).alias("fecha")
            )
    raise ValueError(
        "CSV radial: falta tiempo reconocible (`fecha`, o `anio`/`año` [+ `mes`]). "
        f"Columnas: {cols}"
    )


def _ensure_cast(lf: pl.LazyFrame, *, source: Path) -> pl.LazyFrame:
    cols = lf.collect_schema().names()
    if "acronimo" in cols:
        return lf.with_columns(pl.col("acronimo").cast(pl.Utf8, strict=False).fill_null("").alias("cast"))
    if "cast" in cols:
        return lf.with_columns(pl.col("cast").cast(pl.Utf8, strict=False).fill_null("").alias("cast"))
    # CSV histórico Cudillero suele traer "Est" (→ "est" tras normalización)
    if "est" in cols:
        return lf.with_columns(pl.col("est").cast(pl.Utf8, strict=False).fill_null("").alias("cast"))
    if "estacion" in cols:
        return lf.with_columns(pl.col("estacion").cast(pl.Utf8, strict=False).fill_null("").alias("cast"))
    return lf.with_row_index("_rid").with_columns(
        pl.concat_str(
            [pl.lit(source.stem), pl.lit("_"), pl.col("_rid").cast(pl.Utf8)],
            separator="",
        ).alias("cast")
    ).drop("_rid")


def _read_csv_resilient(source: Path) -> tuple[pl.DataFrame, str]:
    """
    Lee CSV con estrategias progresivas para tolerar ficheros reales heterogéneos.

    Devuelve `(dataframe, strategy_name)` para dejar traza en el reporte.
    """
    attempts: list[tuple[str, dict[str, object]]] = [
        (
            "comma_standard",
            {
                "separator": ",",
                "encoding": "utf8-lossy",
                "ignore_errors": False,
            },
        ),
        (
            "comma_ignore_errors",
            {
                "separator": ",",
                "encoding": "utf8-lossy",
                "ignore_errors": True,
            },
        ),
        (
            "semicolon_standard",
            {
                "separator": ";",
                "encoding": "utf8-lossy",
                "ignore_errors": False,
            },
        ),
        (
            "comma_no_quote",
            {
                "separator": ",",
                "encoding": "utf8-lossy",
                "ignore_errors": True,
                "quote_char": None,
            },
        ),
    ]

    common_kwargs: dict[str, object] = {
        "infer_schema_length": 50_000,
        "try_parse_dates": True,
        "null_values": ["", "NA", "NaN", "null"],
    }

    last_exc: Exception | None = None
    for strategy, kwargs in attempts:
        try:
            df = pl.read_csv(source, **common_kwargs, **kwargs)
            # Si detecta una única columna, normalmente hubo mal separador o quote roto.
            if df.width <= 1:
                raise ValueError(
                    f"Lectura CSV degenerada ({df.width} columna). "
                    f"Strategy={strategy}. Columnas={df.columns}"
                )
            return df, strategy
        except Exception as exc:  # pragma: no cover - fallback path
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No se pudo leer el CSV con ninguna estrategia.")


class RadialCsvReader:
    """Un CSV tabular por filas (profundidad, T, S, estación, fecha/lance)."""

    def read(self, source: Path, *, staging_dir: Path) -> ReadResult:
        staging_dir.mkdir(parents=True, exist_ok=True)

        df, strategy = _read_csv_resilient(source)

        lf = df.lazy()
        lf = _lower_columns(lf)
        lf = _ensure_fecha(lf)
        lf = _ensure_cast(lf, source=source)
        lf = lf.with_columns(
            pl.col("cast")
            .map_elements(identify_radial, return_dtype=pl.Utf8)
            .alias("radial_id")
        )

        cols = lf.collect_schema().names()
        handoff = {
            "source": source.name,
            "columns": cols,
            "reader": "RadialCsvReader",
        }
        notes = [
            "Ingesta CSV radial (handoff para pasos posteriores).",
            f"Estrategia de lectura CSV: {strategy}.",
            "IEO_HANDOFF_JSON:" + json.dumps(handoff, ensure_ascii=False),
        ]
        return ReadResult(lazyframe=lf, source=source, notes=notes)

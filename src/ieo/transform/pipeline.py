from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from ieo.io.base import DatasetReader, ReadResult, reader_for_path
from ieo.runtime.paths import RunPaths
from ieo.transform.canonical_schema import CTDCanonicalSchema, normalize_ctd_columns


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """
    Configuración del pipeline.

    Explicación práctica
    --------------------
    Si algo cambia (p.ej. ruta de datos o qué columnas son obligatorias),
    se toca aquí y el resto del pipeline se mantiene estable.
    """

    schema: CTDCanonicalSchema = CTDCanonicalSchema()


class ReaderFactory:
    """
    Fábrica de lectores por formato.

    Nota práctica:
    - El pipeline de producción solo ingiere ``.cnv`` (``CnvReader``). Excel/NetCDF quedan
      disponibles para extensiones futuras vía ``reader_for_path``.
    """

    def __init__(self, *, cnv: DatasetReader, excel: DatasetReader, netcdf: DatasetReader) -> None:
        self._readers = {"cnv": cnv, "excel": excel, "netcdf": netcdf}

    def reader_for(self, source: Path) -> DatasetReader:
        key = reader_for_path(source)
        return self._readers[key]


def build_canonical_lazyframe(
    *,
    source: Path,
    run_paths: RunPaths,
    factory: ReaderFactory,
    config: PipelineConfig,
    run_id: str,
) -> tuple[pl.LazyFrame, list[str]]:
    """
    Lee un dataset (``.cnv`` en producción) y devuelve un LazyFrame canónico.
    """

    run_paths.ensure()
    reader = factory.reader_for(source)
    result: ReadResult = reader.read(source, staging_dir=run_paths.staging_dir)

    lf = normalize_ctd_columns(result.lazyframe, schema=config.schema)

    # Enriquecimiento mínimo para trazabilidad (sin materializar el dataset)
    s = config.schema
    lf = lf.with_columns(
        [
            pl.lit(run_id).alias(s.run_id),
            pl.lit(source.name).alias(s.source_file),
        ]
    )

    # Row id estable dentro del artefacto canónico
    lf = lf.with_row_index(name=s.row_id, offset=0)

    # Validación de columnas requeridas (fallo temprano con mensaje claro)
    cols = lf.collect_schema().names()
    missing = [c for c in s.required_columns() if c not in cols]
    notes = list(result.notes)
    if missing:
        raise ValueError(f"Faltan columnas requeridas tras normalización: {missing}. Columnas: {cols}")

    return lf, notes


def write_parquet(lf: pl.LazyFrame, out_path: Path) -> None:
    """
    Materializa un LazyFrame y lo guarda en Parquet.

    Práctico:
    - Parquet es rápido y ocupa menos.
    - Es el “artefacto canónico” que usarán los siguientes pasos.
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lf.sink_parquet(str(out_path))


def dataset_metrics(lf: pl.LazyFrame) -> dict[str, Any]:
    """
    Métricas básicas del dataset (baratas) para reportes.
    """

    schema = lf.collect_schema()
    n_cols = len(schema)
    # Nota: contar filas fuerza materialización parcial; en producción es aceptable en checkpoints.
    n_rows = lf.select(pl.len()).collect().item()
    return {"n_rows": int(n_rows), "n_cols": int(n_cols), "columns": schema.names()}


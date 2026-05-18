from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import polars as pl


@dataclass(frozen=True, slots=True)
class ReadResult:
    """
    Resultado de lectura (siempre LazyFrame).

    Explicación práctica
    --------------------
    Un `LazyFrame` permite preparar el trabajo sin cargar todo en memoria.
    El pipeline solo "materializa" datos al final del paso (`collect()` implícito
    al escribir Parquet).
    """

    lazyframe: pl.LazyFrame
    source: Path
    notes: list[str]


class DatasetReader(Protocol):
    """
    Contrato de un lector de datasets.

    Diseño:
    - Cada lector conoce un formato concreto (CNV, Excel, NetCDF).
    - Todos devuelven el mismo tipo de salida (LazyFrame canónico).
    """

    def read(self, source: Path, *, staging_dir: Path) -> ReadResult: ...


def reader_for_path(source: Path) -> str:
    """
    Devuelve un id de lector basado en extensión.

    Extensiones reconocidas
    -----------------------
    - ``.cnv``              → ``"cnv"``   (SeaBird CTD)
    - ``.xls`` / ``.xlsx``  → ``"excel"``
    - ``.nc`` / ``.netcdf`` → ``"netcdf"``
    """
    ext = source.suffix.lower()
    if ext == ".cnv":
        return "cnv"
    if ext in (".xls", ".xlsx"):
        return "excel"
    if ext in (".nc", ".netcdf"):
        return "netcdf"
    raise ValueError(f"Formato no soportado: {source.name} ({ext})")

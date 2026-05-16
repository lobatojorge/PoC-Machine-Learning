from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ieo.io.base import ReadResult


@dataclass(frozen=True, slots=True)
class NetCDFReader:
    """
    Lector “enchufable” para NetCDF (Fase 2).

    Explicación práctica
    --------------------
    Hoy NO implementa el parsing. Solo deja el contrato preparado.
    Si intentas usarlo ahora, el error será explícito y accionable.
    """

    def read(self, source: Path, *, staging_dir: Path) -> ReadResult:
        raise NotImplementedError(
            "NetCDF aún no implementado. "
            "Fase 2: leer con xarray/netcdf4, mapear a esquema canónico, y devolver LazyFrame."
        )


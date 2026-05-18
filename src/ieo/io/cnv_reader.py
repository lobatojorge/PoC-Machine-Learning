"""
Lector de ficheros SeaBird .cnv → LazyFrame normalizado.

Formato típico IEO (SBE 19/25, SeaSoft)
--------------------------------------
- Metadatos con ``*`` y ``**`` (estación, posición, etc.).
- Variables: ``# name N = prSM: ...``, ``t090C``, ``c0S/m``, ``sal00``, …
- ``# start_time = Jul 17 2001 11:54:25`` (a menudo **sin** columna ``timeJ`` en datos).
- Datos tras ``*END*``, columnas separadas por espacios.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from ieo.io.base import ReadResult
from ieo.io.cnv_header import (
    CNV_NAME_LINE_RE,
    CNV_START_TIME_RE,
    parse_cnv_station_number_from_path,
    parse_cnv_start_time_iso_from_path,
)
from ieo.radiales_catalog import identify_radial

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_cnv_header(lines: list[str]) -> tuple[list[str], str | None, int]:
    col_names: list[str] = []
    start_time_iso: str | None = None
    data_start_line = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper() == "*END*":
            data_start_line = i + 1
            break

        m_name = CNV_NAME_LINE_RE.match(stripped)
        if m_name:
            col_names.append(m_name.group(1).strip().lower())
            continue

        m_time = CNV_START_TIME_RE.search(stripped)
        if m_time and start_time_iso is None:
            mon_str = m_time.group(1).lower()[:3]
            mon = _MONTHS.get(mon_str)
            if mon:
                day = int(m_time.group(2))
                year = int(m_time.group(3))
                hh, mm, ss = int(m_time.group(4)), int(m_time.group(5)), int(m_time.group(6))
                start_time_iso = f"{year:04d}-{mon:02d}-{day:02d}T{hh:02d}:{mm:02d}:{ss:02d}"

    return col_names, start_time_iso, data_start_line


class CnvReader:
    """Lector de ficheros SeaBird .cnv."""

    def read(self, source: Path, *, staging_dir: Path) -> ReadResult:
        staging_dir.mkdir(parents=True, exist_ok=True)

        raw_text = source.read_text(encoding="latin-1", errors="replace")
        all_lines = raw_text.splitlines()

        col_names, start_time_iso, data_start_line = _parse_cnv_header(all_lines)
        if start_time_iso is None:
            start_time_iso = parse_cnv_start_time_iso_from_path(source)

        if not col_names:
            raise ValueError(
                f"No se encontraron columnas en la cabecera de {source.name}. "
                "¿Es un fichero .cnv de SeaBird válido?"
            )

        data_lines = all_lines[data_start_line:]
        if not data_lines:
            raise ValueError(f"No se encontraron datos tras la cabecera de {source.name}.")

        rows: list[list[float]] = []
        for raw_line in data_lines:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            try:
                values = [float(v) for v in stripped.split()]
            except ValueError:
                continue
            while len(values) < len(col_names):
                values.append(float("nan"))
            rows.append(values[:len(col_names)])

        if not rows:
            raise ValueError(f"El fichero {source.name} no contiene filas de datos válidas.")

        df = pl.DataFrame(
            {name: [row[i] for row in rows] for i, name in enumerate(col_names)},
            schema={name: pl.Float64 for name in col_names},
        )

        lf = df.lazy()

        schema_cols = lf.collect_schema().names()
        if "fecha" not in schema_cols and start_time_iso is not None:
            ts = pl.lit(start_time_iso).str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False)
            lf = lf.with_columns(ts.alias("fecha"))

        st_num = parse_cnv_station_number_from_path(source)
        if st_num is not None and "estacion" not in schema_cols:
            lf = lf.with_columns(pl.lit(st_num).cast(pl.Int32).alias("estacion"))

        if "cast" not in schema_cols and "acronimo" not in lf.collect_schema().names():
            lf = lf.with_columns(pl.lit(source.stem).alias("cast"))

        cast_col = "cast" if "cast" in lf.collect_schema().names() else None
        if cast_col:
            lf = lf.with_columns(
                pl.col(cast_col)
                .map_elements(identify_radial, return_dtype=pl.Utf8)
                .alias("radial_id")
            )

        handoff = {
            "source": source.name,
            "columns": lf.collect_schema().names(),
            "reader": "CnvReader",
            "start_time_iso": start_time_iso,
            "cnv_columns_raw": col_names,
            "station_from_header": st_num,
        }
        notes = [
            "Ingesta fichero SeaBird .cnv (handoff para pasos posteriores).",
            "IEO_HANDOFF_JSON:" + json.dumps(handoff, ensure_ascii=False),
        ]
        return ReadResult(lazyframe=lf, source=source, notes=notes)

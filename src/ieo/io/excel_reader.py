from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ieo.io.base import ReadResult


@dataclass(frozen=True, slots=True)
class ExcelReader:
    """
    Lector de Excel sin Pandas.

    Implementación
    -------------
    Usa `python-calamine` para leer `.xls/.xlsx` y devuelve un LazyFrame.

    Nota práctica para usuarios no técnicos
    --------------------------------------
    Si el Excel está dañado o falta la dependencia, el error será directo
    (no se oculta).
    """

    sheet_name: str | None = None

    def read(self, source: Path, *, staging_dir: Path) -> ReadResult:
        if not source.exists():
            raise FileNotFoundError(str(source))

        try:
            from python_calamine import CalamineWorkbook  # type: ignore[import-untyped]
        except Exception as exc:  # pragma: no cover
            raise ImportError(
                "Falta dependencia para leer Excel sin pandas: `python-calamine`."
            ) from exc

        wb = CalamineWorkbook.from_path(str(source))
        sheet_names = wb.sheet_names
        if not sheet_names:
            raise ValueError("Excel sin hojas.")

        sheet = self.sheet_name or sheet_names[0]
        if sheet not in sheet_names:
            sheet = sheet_names[0]

        rows = wb.get_sheet_by_name(sheet).to_python()  # list[list[Any]]
        if not rows:
            raise ValueError("Hoja Excel vacía.")

        header = [str(x).strip() for x in rows[0]]
        data_rows = rows[1:]

        # `pl.DataFrame` aquí es inevitable (el Excel es in-memory),
        # pero a partir de aquí volvemos a LazyFrame.
        df = pl.DataFrame(data_rows, schema=header, orient="row")
        lf = df.lazy()

        notes = [
            "Excel leído sin pandas (python-calamine).",
            f"sheet={sheet!r}",
            f"n_sheets={len(sheet_names)}",
        ]
        return ReadResult(lazyframe=lf, source=source, notes=notes)


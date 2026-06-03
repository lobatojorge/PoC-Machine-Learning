"""Cabecera SBE: año de muestreo, estación desde carpeta y meses ES."""

from __future__ import annotations

from pathlib import Path

from ieo.io.cnv_header import (
    parse_cnv_start_time_iso_from_path,
    parse_station_from_folder_name,
    reconcile_start_time_year,
    year_from_filename_stem,
    year_from_path_segments,
)
from ieo.io.cnv_reader import CnvReader


def test_year_from_path_segments() -> None:
    p = Path("data/cnv/2005/sub/gnov105.cnv")
    assert year_from_path_segments(p) == 2005


def test_year_from_filename_apr94() -> None:
    assert year_from_filename_stem("apr94") == 1994
    assert year_from_filename_stem("aug93") == 1993


def test_year_from_filename_tail_gnov105() -> None:
    assert year_from_filename_stem("gnov105") == 2005
    assert year_from_filename_stem("cnov117") == 2017


def test_reconcile_replaces_wrong_header_year() -> None:
    iso = "2080-11-05T12:00:00"
    fixed = reconcile_start_time_year(iso, Path("data/cnv/2005/gnov105.cnv"))
    assert fixed is not None
    assert fixed.startswith("2005-11-05")


def test_station_from_st_folder(tmp_path: Path) -> None:
    st1 = tmp_path / "St.1 CNVs"
    st1.mkdir(parents=True)
    f = st1 / "apr94.cnv"
    f.write_text(
        "\n".join(
            [
                "* Sea-Bird",
                "# name 0 = t068C: T",
                "# name 1 = depSM: depth",
                "# start_time = Apr 10 1993 10:00:00",
                "*END*",
                "1 12.0 5.0",
            ]
        ),
        encoding="latin-1",
    )
    assert parse_station_from_folder_name(f) == 1
    reader = CnvReader()
    res = reader.read(f, staging_dir=tmp_path / "st")
    pdf = res.lazyframe.collect().to_pandas()
    assert "estacion" in pdf.columns
    assert int(pdf["estacion"].iloc[0]) == 1
    ts = parse_cnv_start_time_iso_from_path(f)
    assert ts is not None
    assert ts.startswith("1994-")

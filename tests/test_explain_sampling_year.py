# -*- coding: utf-8 -*-
"""Explicacion del ano de muestreo en rutas .cnv."""

from pathlib import Path

from ieo.io.cnv_header import explain_sampling_year, year_from_filename_stem


def test_year_from_filename_apr94() -> None:
    assert year_from_filename_stem("apr94") == 1994


def test_explain_sampling_year_rule_path(tmp_path: Path) -> None:
    p = tmp_path / "2019" / "foo.cnv"
    p.parent.mkdir(parents=True)
    p.write_text("# start_time = Jul 17 2001 11:54:25\n*END*\n", encoding="latin-1")
    info = explain_sampling_year(p)
    assert info["year_from_path"] == 2019
    assert info["rule"] == "path"

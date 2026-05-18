"""Tests del índice geográfico de radiales desde cabeceras .cnv."""

from __future__ import annotations

from pathlib import Path

from ieo.reports.radial_cnv_geo import build_radial_geo_index


def test_build_radial_geo_index_empty(tmp_path: Path) -> None:
    (tmp_path / "data" / "cnv").mkdir(parents=True)
    idx = build_radial_geo_index(tmp_path)
    assert idx.cities == []
    assert idx.n_cnv_scanned == 0

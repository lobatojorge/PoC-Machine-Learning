"""Tests de clasificación radial en cabeceras .cnv (sin datos IEO reales)."""

from __future__ import annotations

from pathlib import Path

from ieo.io.cnv_radial import (
    classify_cnv_radial,
    classify_cnv_radial_detailed,
    filter_paths_by_radial,
    is_rcan_campaign,
    read_cnv_radial_hints,
)
from ieo.radiales_catalog import RADIAL_ID_CORUNA, RADIAL_ID_CUDILLERO, RADIAL_ID_GIJON, RADIAL_ID_SANTANDER


def _write_cnv(tmp_path: Path, name: str, header_lines: list[str], data_line: str = "1.0 2.0 3.0 0\n") -> Path:
    p = tmp_path / name
    body = "\n".join(header_lines) + "\n*END*\n" + data_line
    p.write_text(body, encoding="latin-1")
    return p


def test_classify_cudillero_by_filename_and_coords(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "jul301.cnv",
        [
            "* Sea-Bird",
            "** Ship: RIOJA",
            "** Cruise:",
            "** Station: 2",
            "** Latitude: 43 31 500",
            "** Longitude: 4 30",
            "# name 0 = prSM:",
            "# name 1 = t090C:",
            "# start_time = Jul 17 2001 11:54:25",
        ],
    )
    assert classify_cnv_radial(p) == RADIAL_ID_CUDILLERO


def test_classify_gijon_by_cruise_and_prefix(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "gdic102rt.cnv",
        [
            "** Cruise: Radial de Gij",
            "** Latitude: 43 34.84 N",
            "** Longitude: 005 36.45 W",
            "# name 0 = prSM:",
            "# name 1 = par:",
        ],
    )
    assert classify_cnv_radial(p) == RADIAL_ID_GIJON


def test_classify_santander_by_cruise(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "abr202.cnv",
        [
            "** Cruise: Radial Santander",
            "# name 0 = prSM:",
            "# name 1 = t090C:",
        ],
    )
    assert classify_cnv_radial(p) == RADIAL_ID_SANTANDER


def test_read_cruise_line(tmp_path: Path) -> None:
    p = _write_cnv(tmp_path, "x.cnv", ["** Cruise: Radial Santander", "# name 0 = t090C:"])
    hints = read_cnv_radial_hints(p)
    assert "Santander" in hints.cruise


def test_filter_paths_by_radial_gijon(tmp_path: Path) -> None:
    g = _write_cnv(tmp_path, "gjul101.cnv", ["** Cruise: Radial Gijón", "# name 0 = t090C:"])
    c = _write_cnv(tmp_path, "jul301.cnv", ["** Cruise:", "** Latitude: 43 31 500", "# name 0 = t090C:"])
    kept, _, _ = filter_paths_by_radial([g, c], RADIAL_ID_GIJON)
    assert kept == [g]


def test_rcan_campaign_not_santander_by_name(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "rcan_test.cnv",
        [
            "** Cruise: RCAN_04.2017",
            "** Latitude: 43 34.00 N",
            "** Longitude: 005 36.00 W",
            "# name 0 = t090C:",
        ],
    )
    assert is_rcan_campaign("RCAN_04.2017")
    assert classify_cnv_radial(p) == RADIAL_ID_GIJON


def test_rcan_coords_santander(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "rcan2.cnv",
        [
            "** Cruise: RCAN201705",
            "** Latitude: 43 40.00 N",
            "** Longitude: 003 47.00 W",
            "# name 0 = t090C:",
        ],
    )
    assert classify_cnv_radial(p) == RADIAL_ID_SANTANDER


def test_coruna_xn_coords(tmp_path: Path) -> None:
    """Coordenadas típicas Galicia occidental (no mar central N de Gijón)."""
    p = _write_cnv(
        tmp_path,
        "xnamay13rt.cnv",
        [
            "** Cruise: Radiales Cantabrico",
            "** Latitude: 43 23.00 N",
            "** Longitude: 008 24.00 W",
            "# name 0 = t090C:",
        ],
    )
    assert classify_cnv_radial(p) == RADIAL_ID_CORUNA


def test_geo_wins_over_conflicting_cruise(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "conflict.cnv",
        [
            "** Cruise: Radial Santander",
            "** Latitude: 43 34.00 N",
            "** Longitude: 005 36.00 W",
            "# name 0 = t090C:",
        ],
    )
    det = classify_cnv_radial_detailed(p)
    assert det.radial_id == RADIAL_ID_GIJON
    assert det.conflict_cruise_vs_geo is True


def test_sanatnder_typo(tmp_path: Path) -> None:
    p = _write_cnv(
        tmp_path,
        "typo.cnv",
        [
            "** Cruise: Radial de Sanatnder",
            "** Latitude: 43 39.00 N",
            "** Longitude: 003 47.00 W",
            "# name 0 = t090C:",
        ],
    )
    assert classify_cnv_radial(p) == RADIAL_ID_SANTANDER

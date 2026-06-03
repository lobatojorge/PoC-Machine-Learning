"""Tests de ``classify_radial_by_position`` (Cantábrico / A Coruña)."""

from __future__ import annotations

import pytest

from ieo.io.cnv_radial import classify_radial_by_position
from ieo.radiales_catalog import RADIAL_ID_CORUNA, RADIAL_ID_CUDILLERO, RADIAL_ID_GIJON, RADIAL_ID_SANTANDER


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        # Mar al norte de Gijón (antes mal clasificado como Coruña)
        (43.9, -5.5, RADIAL_ID_GIJON),
        (44.0, -5.3, RADIAL_ID_GIJON),
        # Aprox. A Coruña costa / plataforma occidental
        (43.37, -8.4, RADIAL_ID_CORUNA),
        (43.55, -7.5, RADIAL_ID_CORUNA),
        # Asturias / Cudillero
        (43.55, -6.2, RADIAL_ID_CUDILLERO),
        (43.6, -6.1, RADIAL_ID_CUDILLERO),
        # Gijón
        (43.55, -5.67, RADIAL_ID_GIJON),
        # Santander (más al este)
        (43.46, -3.8, RADIAL_ID_SANTANDER),
    ],
)
def test_classify_radial_by_position_reference_points(
    lat: float, lon: float, expected: str
) -> None:
    assert classify_radial_by_position(lat, lon) == expected


def test_classify_radial_by_position_none_outside_box() -> None:
    assert classify_radial_by_position(None, -5.0) is None
    assert classify_radial_by_position(43.5, None) is None
    assert classify_radial_by_position(42.0, -6.0) is None
    assert classify_radial_by_position(45.0, -6.0) is None

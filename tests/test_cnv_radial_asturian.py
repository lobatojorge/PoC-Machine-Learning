# -*- coding: utf-8 -*-
from ieo.io.cnv_radial import (
    LOCALITY_ALIASES_ASTURIAN,
    _radial_from_cruise_explicit,
    normalize_cruise_text,
)


def test_normalize_cruise_strips_accents() -> None:
    assert normalize_cruise_text("Radial Xix\u00f3n") == "radial xixon"


def test_cuideiru_maps_to_cudillero() -> None:
    cruise = "Radial 2001 Cuideiru Asturies"
    assert _radial_from_cruise_explicit(cruise) == "cudillero"
    assert "cuideiru" in LOCALITY_ALIASES_ASTURIAN


def test_xixon_maps_to_gijon() -> None:
    assert _radial_from_cruise_explicit("Campana Xixon 2020") == "gijon"

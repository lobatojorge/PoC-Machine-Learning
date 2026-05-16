"""Tests del catálogo de radiales (sin Streamlit)."""

from __future__ import annotations

import pandas as pd

from ieo.radiales_catalog import (
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_SANTANDER,
    attach_radial_id,
    filter_dataframe_to_radial,
    identify_radial,
)


def test_identify_cudillero_and_santander() -> None:
    assert identify_radial("ENE00E1.CNV|bajada|E1CU") == RADIAL_ID_CUDILLERO
    assert identify_radial("ene401.cnv|bajada|E4SA") == RADIAL_ID_SANTANDER
    assert identify_radial("AGL") == RADIAL_ID_SANTANDER
    assert identify_radial("") is None


def test_longer_coruna_code_wins() -> None:
    assert identify_radial("foo|E3BCO|bar") == "coruna"
    assert identify_radial("foo|E3CCO") == "coruna"


def test_filter_dataframe_to_radial() -> None:
    df = pd.DataFrame(
        {
            "acronimo": ["x|E1CU", "x|E4SA"],
            "estacion": [1, 4],
        }
    )
    out, dropped = filter_dataframe_to_radial(df, RADIAL_ID_CUDILLERO)
    assert len(out) == 1
    assert dropped == 1
    assert out.iloc[0]["estacion"] == 1

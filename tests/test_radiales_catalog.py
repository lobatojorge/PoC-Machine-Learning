"""Tests del catálogo de radiales (sin Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ieo.radiales_catalog import (
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_GIJON,
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


def test_attach_radial_id_backfill_from_source_file(tmp_path: Path) -> None:
    cnv = tmp_path / "cnv"
    (cnv / "2001").mkdir(parents=True)
    p = cnv / "2001" / "gjul101.cnv"
    p.write_text(
        "\n".join(
            [
                "* Sea-Bird",
                "# name 0 = t068: T",
                "# start_time = Jul 10 2001 10:00:00",
                "*END*",
                "1 12.0",
            ]
        ),
        encoding="latin-1",
    )
    df = pd.DataFrame(
        {
            "source_file": ["gjul101.cnv", "ene401.cnv"],
            "radial_id": [pd.NA, pd.NA],
            "estacion": [1, 1],
        }
    )
    out = attach_radial_id(df, cnv_root=cnv)
    assert out.loc[0, "radial_id"] == RADIAL_ID_GIJON

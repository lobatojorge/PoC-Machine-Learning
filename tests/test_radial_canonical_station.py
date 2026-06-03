# -*- coding: utf-8 -*-
"""Estacion canonica del transecto IEO."""

from __future__ import annotations

import pandas as pd

from ieo.radial_canonical_station import (
    apply_canonical_station_column,
    resolve_canonical_station,
)


def test_e2gi_from_cast_stem() -> None:
    assert resolve_canonical_station("gijon", cast="rcan202510E2GIcast018") == 2


def test_st_folder_cudillero() -> None:
    assert (
        resolve_canonical_station(
            "cudillero",
            station_folder=3,
            station_sbe=0,
        )
        == 3
    )


def test_station_sbe_zero_without_code_returns_none_for_gijon() -> None:
    assert resolve_canonical_station("gijon", station_sbe=0) is None


def test_apply_overwrites_estacion() -> None:
    df = pd.DataFrame(
        {
            "cast": ["fooE3GIbar"],
            "estacion": [12],
            "source_file": ["x.cnv"],
        }
    )
    out = apply_canonical_station_column(df, "gijon", overwrite=True)
    assert int(out["estacion"].iloc[0]) == 3

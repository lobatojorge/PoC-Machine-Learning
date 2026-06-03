"""Normalización canónica: columnas SBE antiguas (St.* CNVs)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ieo.io.cnv_reader import CnvReader
from ieo.transform.canonical_schema import (
    CTDCanonicalSchema,
    ensure_profundidad_m_pandas,
    normalize_ctd_columns,
)


def test_normalize_maps_t068c_and_deps(tmp_path: Path) -> None:
    cnv = tmp_path / "legacy.cnv"
    cnv.write_text(
        "\n".join(
            [
                "* Sea-Bird",
                "# name 0 = t068C: Temperature",
                "# name 1 = pr: pressure",
                "# name 2 = depS: depth",
                "# start_time = Jan 13 2000 10:28:25",
                "*END*",
                "1 12.0 2.0 3.0",
            ]
        ),
        encoding="latin-1",
    )
    reader = CnvReader()
    lf = reader.read(cnv, staging_dir=tmp_path / "st").lazyframe
    out = normalize_ctd_columns(lf, schema=CTDCanonicalSchema()).collect()
    assert "temperatura_c" in out.columns
    assert "profundidad_m" in out.columns
    assert out.height >= 1
    assert out["temperatura_c"].null_count() < out.height
    assert out["profundidad_m"].null_count() < out.height


def test_normalize_feb00_style_sbe_columns(tmp_path: Path) -> None:
    """Columnas típicas St.* (``t068``, ``deps``, ``pr``) como en ``feb00.cnv``."""
    cnv = tmp_path / "feb00_style.cnv"
    cnv.write_text(
        "\n".join(
            [
                "* Sea-Bird",
                "# name 0 = scan: scan number",
                "# name 1 = t068: temperature",
                "# name 2 = c0S/m: conductivity",
                "# name 3 = pr: pressure",
                "# name 4 = par: par",
                "# name 5 = v3: voltage",
                "# name 6 = depS: depth",
                "# name 7 = potemp068: pot temp",
                "# name 8 = sal00: salinity",
                "# name 9 = sigma-t00: sigma",
                "# name 10 = N^2: N2",
                "# name 11 = N: N",
                "# name 12 = flag: flag",
                "# start_time = Feb 22 2000 14:23:46",
                "*END*",
                "1 12.0 4.0 2.0 0.1 0.1 1.5 12.0 35.0 26.0 0.0 0.0 0",
                "2 12.1 4.0 3.0 0.1 0.1 2.5 12.1 35.0 26.0 0.0 0.0 0",
            ]
        ),
        encoding="latin-1",
    )
    lf = CnvReader().read(cnv, staging_dir=tmp_path / "st").lazyframe
    out = normalize_ctd_columns(lf, schema=CTDCanonicalSchema()).collect()
    assert "profundidad_m" in out.columns
    assert "temperatura_c" in out.columns
    assert out["profundidad_m"].null_count() == 0


def test_ensure_profundidad_m_from_deps_only() -> None:
    import pandas as pd

    df = pd.DataFrame({"deps": [1.0, 2.0], "t068": [12.0, 12.1]})
    out = ensure_profundidad_m_pandas(df)
    assert "profundidad_m" in out.columns
    assert list(out["profundidad_m"]) == [1.0, 2.0]

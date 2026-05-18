"""Bandas Marcos iid (sin AR)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _load_analysis():
    key = "ieo_02_analysis_bands_test"
    if key in sys.modules:
        return sys.modules[key]
    path = Path(__file__).resolve().parents[1] / "src" / "02_analysis.py"
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    sys.modules[key] = mod
    return mod


def test_holdout_bands_constant_width() -> None:
    mod = _load_analysis()
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    rs = pd.Series(0.1 * np.random.default_rng(0).standard_normal(24), index=idx)
    cutoff = pd.Timestamp("2021-01-01")
    out, meta = mod.marcos_iid_bands_on_residuals(rs, cutoff_holdout_start=cutoff, holdout_months=6, fechas=idx)
    assert meta["error_model"] == "marcos_iid_gaussian"
    hold = out.loc[(out["fecha"] >= cutoff) & out["resid_fc_hi_95"].notna()]
    widths = (hold["resid_fc_hi_95"] - hold["resid_fc_lo_95"]).dropna()
    assert len(widths) >= 2
    assert float(widths.std()) < 1e-9

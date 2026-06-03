# -*- coding: utf-8 -*-
"""Test for building ATAC monthly figure."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from atac_monthly_report import build_atac_monthly_figure


def test_build_atac_monthly_figure_success() -> None:
    project_root = Path(__file__).resolve().parents[1]
    
    # Create mock monthly data with at least 15 observations to avoid holdout/model issues
    dates = pd.date_range("2023-01-01", periods=18, freq="MS")
    df = pd.DataFrame({
        "fecha": dates,
        "temp_5m": [15.0 + i % 3 for i in range(18)],
    })
    
    res = build_atac_monthly_figure(
        project_root=project_root,
        monthly_5m=df,
        station_label="Estación de Test",
        holdout_months=1,
        var_label="Temperatura",
        var_units="°C",
        depth_m=5,
    )
    
    assert res.fig is not None
    assert "Temperatura" in res.fig.layout.title.text
    assert "¿Cómo se agrupan los datos si hay varios lances" in res.footer_md

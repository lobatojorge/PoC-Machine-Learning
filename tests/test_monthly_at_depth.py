# -*- coding: utf-8 -*-
"""Monthly aggregation at fixed depth: deepest cast per month."""

from __future__ import annotations

import pandas as pd

from ieo.reports.monthly_at_depth import monthly_value_at_depth


def test_monthly_picks_deepest_cast_same_month() -> None:
    df = pd.DataFrame(
        {
            "fecha": pd.to_datetime(
                [
                    "2025-10-01",
                    "2025-10-01",
                    "2025-10-02",
                    "2025-10-02",
                    "2025-10-03",
                    "2025-10-03",
                    "2025-10-03",
                ]
            ),
            "profundidad_m": [0.0, 5.0, 0.0, 5.0, 0.0, 5.0, 80.0],
            "temperatura_c": [18.0, 20.0, 17.0, 19.0, 16.0, 14.0, 14.0],
            "estacion": [1, 1, 1, 1, 1, 1, 1],
            "acronimo": ["shallow", "shallow", "mid", "mid", "deep", "deep", "deep"],
        }
    )
    monthly, diag = monthly_value_at_depth(
        df,
        col_value="temperatura_c",
        target_depth_m=5.0,
    )
    assert len(monthly) == 1
    assert float(monthly.iloc[0]["valor_prof"]) == 14.0
    assert diag["n_casts"] == 3

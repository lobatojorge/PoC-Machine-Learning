"""Isolation Forest con matrices de solo lectura (regresión sabr417)."""

from __future__ import annotations

import polars as pl

from ieo.observability.anomaly import IsolationForestConfig, detect_anomalies_isolation_forest


def test_detect_anomalies_on_readonly_numpy_view() -> None:
    df = pl.DataFrame(
        {
            "row_id": [0, 1, 2, 3, 4],
            "profundidad_m": [1.0, 2.0, 3.0, 4.0, 5.0],
            "temperatura_c": [10.0, 10.1, 10.2, 50.0, 10.3],
            "salinidad_psu": [35.0, 35.1, 35.0, 35.2, 35.1],
        }
    )
    # Vista de solo lectura similar a la que devolvía polars en algunos Parquet.
    arr = df.select(["profundidad_m", "temperatura_c", "salinidad_psu"]).to_numpy()
    arr.setflags(write=False)
    assert not arr.flags.writeable

    outs = detect_anomalies_isolation_forest(
        df=df,
        row_id_col="row_id",
        config=IsolationForestConfig(n_estimators=48),
        run_id="test",
        source_file="test.parquet",
        n_jobs=1,
    )
    assert outs.clean.height >= 1
    assert "anomaly_score" in outs.clean.columns

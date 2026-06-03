"""Tests de paralelización y heurísticas del paso QC."""

from __future__ import annotations

from pathlib import Path

from ieo.pipeline_qc import effective_n_estimators, qc_outputs_up_to_date


def test_effective_n_estimators_scales_down() -> None:
    assert effective_n_estimators(30, cap=200) == 48
    assert effective_n_estimators(500, cap=200) == 200
    assert effective_n_estimators(120, cap=200) == 120


def test_qc_outputs_up_to_date(tmp_path: Path) -> None:
    import os
    import time

    data = tmp_path / "data"
    data.mkdir()
    can = data / "foo.ctd_canonical.parquet"
    clean = data / "foo.ctd_clean.parquet"
    anom = data / "foo.ctd_anomalies.parquet"
    audit = data / "foo.ctd_anomaly_audit.parquet"
    assert not qc_outputs_up_to_date(can, data)

    can.write_bytes(b"x")
    time.sleep(0.05)
    clean.write_bytes(b"y")
    anom.write_bytes(b"z")
    audit.write_bytes(b"w")
    assert qc_outputs_up_to_date(can, data)

    time.sleep(0.05)
    can.write_bytes(b"xx")
    assert not qc_outputs_up_to_date(can, data)

    clean.write_bytes(b"yy")
    anom.write_bytes(b"zz")
    audit.write_bytes(b"ww")
    os.utime(clean, None)
    os.utime(anom, None)
    os.utime(audit, None)
    assert qc_outputs_up_to_date(can, data)

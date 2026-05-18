"""Tests de utilidades puras del visor–pipeline (sin Streamlit)."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

import pipeline_runs as pr


def _minimal_ctd_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2020-01-15", "2020-02-10"]),
            "estacion": [1, 1],
            "cast": ["c1", "c1"],
            "profundidad_m": [2.0, 8.0],
            "temperatura_c": [12.0, 11.5],
            "salinidad_psu": [35.0, 35.1],
            "row_id": [0, 1],
        }
    )


def _write_valid_run(run_root: Path, *, rows: pd.DataFrame | None = None) -> None:
    data_dir = run_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    df = rows if rows is not None else _minimal_ctd_rows()
    df.to_parquet(data_dir / "perfiles_all.ctd_clean.parquet", index=False)
    df.head(0).to_parquet(data_dir / "perfiles_all.ctd_anomalies.parquet", index=False)


def test_list_valid_run_roots_empty(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "outputs" / "runs").mkdir(parents=True)
    assert pr.list_valid_run_roots(root) == []


def test_latest_and_resolve_ui(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    runs = root / "outputs" / "runs"
    runs.mkdir(parents=True)
    old = runs / "run_older"
    new = runs / "run_newer"
    _write_valid_run(old)
    time.sleep(0.05)
    _write_valid_run(new)
    valid = pr.list_valid_run_roots(root)
    assert [p.name for p in valid] == ["run_newer", "run_older"]
    assert pr.latest_valid_run_root(root) == new
    assert pr.resolve_run_root_for_ui(root, pr.LATEST_SENTINEL) == new
    assert pr.resolve_run_root_for_ui(root, "run_older") == old


def test_load_pipeline_viewer_concat_flag(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    rr = root / "outputs" / "runs" / "run_one"
    _write_valid_run(rr)
    # Una fila anómala con mismas columnas
    data_dir = rr / "data"
    clean = pd.read_parquet(data_dir / "perfiles_all.ctd_clean.parquet")
    anom = clean.tail(1).copy()
    clean2 = clean.iloc[:-1]
    clean2.to_parquet(data_dir / "perfiles_all.ctd_clean.parquet", index=False)
    anom.to_parquet(data_dir / "perfiles_all.ctd_anomalies.parquet", index=False)

    out = pr.load_pipeline_viewer_data(rr)
    assert out is not None
    assert "_viewer_anomaly" in out.df_concat_viz.columns
    assert out.df_concat_viz["_viewer_anomaly"].sum() == 1
    assert (~out.df_concat_viz["_viewer_anomaly"]).sum() == len(clean2)


def test_clean_parquet_cache_token_changes(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    rr = root / "outputs" / "runs" / "run_tok"
    _write_valid_run(rr)
    t1 = pr.clean_parquet_cache_token(rr)
    time.sleep(0.05)
    df = pd.read_parquet(rr / "data" / "perfiles_all.ctd_clean.parquet")
    df.to_parquet(rr / "data" / "perfiles_all.ctd_clean.parquet", index=False)
    t2 = pr.clean_parquet_cache_token(rr)
    assert t1 != t2


def test_load_pipeline_viewer_multi_part_clean(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    rr = root / "outputs" / "runs" / "run_parts"
    data_dir = rr / "data"
    data_dir.mkdir(parents=True)
    df_a = _minimal_ctd_rows()
    df_b = df_a.copy()
    df_b["estacion"] = 2
    df_a.to_parquet(data_dir / "cast_a.ctd_clean.parquet", index=False)
    df_b.to_parquet(data_dir / "cast_b.ctd_clean.parquet", index=False)
    out = pr.load_pipeline_viewer_data(rr)
    assert out is not None
    assert len(out.df_clean) == len(df_a) + len(df_b)


def test_read_provenance_dict(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    rr = root / "outputs" / "runs" / "run_prov"
    _write_valid_run(rr)
    (rr / "provenance.json").write_text('{"run_id": "run_prov", "sources": ["x.csv"]}', encoding="utf-8")
    d = pr.read_provenance_dict(rr)
    assert d == {"run_id": "run_prov", "sources": ["x.csv"]}

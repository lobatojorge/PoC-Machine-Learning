"""Rutas bajo data/cnv: carpetas año vs otras convenciones."""

from __future__ import annotations

from pathlib import Path

from ieo.cnv_layout import (
    cnv_data_tree_fingerprint,
    first_segment_under_cnv_root,
    is_non_year_shard_under_cnv,
    is_year_shard_segment,
    non_year_shard_counts,
)


def test_year_shard_segment() -> None:
    assert is_year_shard_segment("2001") is True
    assert is_year_shard_segment("20ab") is False
    assert is_year_shard_segment("St.1 CNVs") is False


def test_non_year_detection(tmp_path: Path) -> None:
    cnv = tmp_path / "cnv"
    (cnv / "2001").mkdir(parents=True)
    (cnv / "St.1 CNVs").mkdir(parents=True)
    a = cnv / "2001" / "a.cnv"
    b = cnv / "St.1 CNVs" / "b.cnv"
    a.write_text("x", encoding="utf-8")
    b.write_text("x", encoding="utf-8")

    assert first_segment_under_cnv_root(cnv, a) == "2001"
    assert first_segment_under_cnv_root(cnv, b) == "St.1 CNVs"
    assert is_non_year_shard_under_cnv(cnv, a) is False
    assert is_non_year_shard_under_cnv(cnv, b) is True

    counts = non_year_shard_counts(cnv, [a, b])
    assert counts == {"St.1 CNVs": 1}


def test_cnv_data_tree_fingerprint(tmp_path: Path) -> None:
    cnv = tmp_path / "cnv"
    cnv.mkdir()
    f = cnv / "a.cnv"
    f.write_text("x", encoding="utf-8")
    tok1 = cnv_data_tree_fingerprint(cnv)
    assert tok1.startswith("1:")
    (cnv / "b.cnv").write_text("z", encoding="utf-8")
    tok2 = cnv_data_tree_fingerprint(cnv)
    assert tok2.startswith("2:")
    assert tok1 != tok2


def test_cnv_data_tree_fingerprint_missing(tmp_path: Path) -> None:
    assert cnv_data_tree_fingerprint(tmp_path / "no_such") == "missing"

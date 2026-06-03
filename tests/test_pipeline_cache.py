"""Caché incremental del pipeline."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ieo.pipeline_cache import (
    artifact_slug,
    entry_matches_file,
    load_manifest,
    publish_canonical_to_cache,
    publish_qc_to_cache,
    save_manifest,
    try_copy_cached_canonical,
    try_copy_cached_qc_triplet,
)


def test_artifact_slug_unique_per_path() -> None:
    a = artifact_slug("2002/a.cnv", "a")
    b = artifact_slug("2003/a.cnv", "a")
    assert a != b


def test_incremental_canonical_roundtrip(tmp_path: Path) -> None:
    project = tmp_path
    cnv = project / "data" / "cnv" / "2020"
    cnv.mkdir(parents=True)
    src = cnv / "cast1.cnv"
    src.write_text("* ship\n", encoding="utf-8")

    manifest = load_manifest(project)
    key = "2020/cast1.cnv"
    run_dir = project / "runs" / "r1" / "data"
    run_dir.mkdir(parents=True)
    run_can = run_dir / "cast1.ctd_canonical.parquet"
    pl.DataFrame({"row_id": [0], "profundidad_m": [1.0], "temperatura_c": [10.0]}).write_parquet(
        run_can
    )

    publish_canonical_to_cache(
        project_root=project,
        source_key=key,
        stem="cast1",
        sha256="abc",
        run_canonical=run_can,
        manifest=manifest,
    )
    save_manifest(project, manifest)

    run2 = project / "runs" / "r2" / "data"
    run2.mkdir(parents=True)
    run_can2 = run2 / "cast1.ctd_canonical.parquet"
    entry = load_manifest(project)["entries"][key]
    assert try_copy_cached_canonical(
        project_root=project,
        source_key=key,
        stem="cast1",
        entry=entry,
        run_canonical=run_can2,
    )
    assert run_can2.is_file()


def test_copy_cached_qc_triplet(tmp_path: Path) -> None:
    project = tmp_path
    manifest = load_manifest(project)
    key = "x/y.cnv"
    slug = artifact_slug(key, "y")
    from ieo.pipeline_cache import _kind_paths, cache_root

    cache = cache_root(project)
    for kind in ("clean", "anomalies", "audit"):
        p = _kind_paths(cache, slug, kind)
        p.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame({"row_id": [0]}).write_parquet(p)

    manifest["entries"][key] = {"slug": slug, "stem": "y", "sha256": "x"}
    run_data = project / "run" / "data"
    run_data.mkdir(parents=True)
    assert try_copy_cached_qc_triplet(
        project_root=project,
        entry=manifest["entries"][key],
        stem="y",
        run_data_dir=run_data,
    )
    assert (run_data / "y.ctd_clean.parquet").is_file()


def test_entry_matches_file(tmp_path: Path) -> None:
    f = tmp_path / "f.cnv"
    f.write_bytes(b"1")
    st = f.stat()
    entry = {"size": st.st_size, "mtime": st.st_mtime}
    assert entry_matches_file(f, entry)
    f.write_bytes(b"12")
    assert not entry_matches_file(f, entry)

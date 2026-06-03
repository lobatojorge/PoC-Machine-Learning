"""
Caché incremental entre ejecuciones del pipeline (ingesta + QC).

El manifiesto ``outputs/pipeline_manifest.json`` indexa cada ``.cnv`` por ruta relativa
bajo ``data/cnv/`` y su SHA256. Los Parquet viven en ``outputs/artifact_cache/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from ieo.runtime.provenance import _sha256_file

PIPELINE_SCHEMA_VERSION = "canonical-ctd-v1"
MANIFEST_NAME = "pipeline_manifest.json"
CACHE_DIR_NAME = "artifact_cache"


def incremental_enabled() -> bool:
    """False si ``IEO_FULL_REBUILD=1`` (reprocesa todo)."""
    return os.environ.get("IEO_FULL_REBUILD", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    )


def manifest_path(project_root: Path) -> Path:
    return project_root / "outputs" / MANIFEST_NAME


def cache_root(project_root: Path) -> Path:
    return project_root / "outputs" / CACHE_DIR_NAME


def artifact_slug(source_key: str, stem: str) -> str:
    """Identificador estable (evita colisiones de ``stem`` en distintas carpetas)."""
    h = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:12]
    safe_stem = stem.replace(" ", "_")[:80]
    return f"{h}_{safe_stem}"


def _kind_paths(cache: Path, slug: str, kind: str) -> Path:
    sub = {"canonical": "canonical", "clean": "clean", "anomalies": "anomalies", "audit": "audit"}[
        kind
    ]
    suffix = {
        "canonical": "ctd_canonical.parquet",
        "clean": "ctd_clean.parquet",
        "anomalies": "ctd_anomalies.parquet",
        "audit": "ctd_anomaly_audit.parquet",
    }[kind]
    return cache / sub / f"{slug}.{suffix}"


def load_manifest(project_root: Path) -> dict[str, Any]:
    path = manifest_path(project_root)
    if not path.is_file():
        return {"schema_version": PIPELINE_SCHEMA_VERSION, "entries": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": PIPELINE_SCHEMA_VERSION, "entries": {}}
    if data.get("schema_version") != PIPELINE_SCHEMA_VERSION:
        return {"schema_version": PIPELINE_SCHEMA_VERSION, "entries": {}}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    return {"schema_version": PIPELINE_SCHEMA_VERSION, "entries": entries}


def save_manifest(project_root: Path, manifest: dict[str, Any]) -> None:
    path = manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _stat_tuple(path: Path) -> tuple[int, float]:
    st = path.stat()
    return int(st.st_size), float(st.st_mtime)


def entry_matches_file(path: Path, entry: dict[str, Any] | None) -> bool:
    if not entry or not path.is_file():
        return False
    try:
        size, mtime = _stat_tuple(path)
    except OSError:
        return False
    return int(entry.get("size", -1)) == size and abs(float(entry.get("mtime", -1)) - mtime) < 1e-6


def resolve_file_sha256(path: Path, entry: dict[str, Any] | None) -> str:
    if entry and entry_matches_file(path, entry) and entry.get("sha256"):
        return str(entry["sha256"])
    return _sha256_file(path)


def try_copy_cached_canonical(
    *,
    project_root: Path,
    source_key: str,
    stem: str,
    entry: dict[str, Any],
    run_canonical: Path,
) -> bool:
    """Copia canónico de caché al run si SHA y fichero en caché coinciden."""
    slug = entry.get("slug") or artifact_slug(source_key, stem)
    cached = _kind_paths(cache_root(project_root), slug, "canonical")
    if not cached.is_file():
        return False
    run_canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached, run_canonical)
    return True


def try_copy_cached_qc_triplet(
    *,
    project_root: Path,
    entry: dict[str, Any],
    stem: str,
    run_data_dir: Path,
) -> bool:
    """Copia clean/anomalies/audit de caché al directorio del run."""
    slug = str(entry.get("slug", ""))
    if not slug:
        return False
    cache = cache_root(project_root)
    src_clean = _kind_paths(cache, slug, "clean")
    src_anom = _kind_paths(cache, slug, "anomalies")
    src_audit = _kind_paths(cache, slug, "audit")
    if not (src_clean.is_file() and src_anom.is_file() and src_audit.is_file()):
        return False
    dst_clean = run_data_dir / f"{stem}.ctd_clean.parquet"
    dst_anom = run_data_dir / f"{stem}.ctd_anomalies.parquet"
    dst_audit = run_data_dir / f"{stem}.ctd_anomaly_audit.parquet"
    for src, dst in ((src_clean, dst_clean), (src_anom, dst_anom), (src_audit, dst_audit)):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True


def publish_canonical_to_cache(
    *,
    project_root: Path,
    source_key: str,
    stem: str,
    sha256: str,
    run_canonical: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    slug = artifact_slug(source_key, stem)
    cache = cache_root(project_root)
    cached = _kind_paths(cache, slug, "canonical")
    cached.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_canonical, cached)
    size, mtime = _stat_tuple(run_canonical)
    entry = {
        "slug": slug,
        "stem": stem,
        "sha256": sha256,
        "canonical_sha256": sha256,
        "size": size,
        "mtime": mtime,
        "canonical": str(cached.relative_to(project_root)).replace("\\", "/"),
    }
    manifest.setdefault("entries", {})[source_key] = entry
    return entry


def publish_qc_to_cache(
    *,
    project_root: Path,
    source_key: str,
    stem: str,
    run_data_dir: Path,
    manifest: dict[str, Any],
) -> None:
    entries = manifest.setdefault("entries", {})
    entry = entries.get(source_key) or {}
    slug = str(entry.get("slug") or artifact_slug(source_key, stem))
    cache = cache_root(project_root)
    for kind, stem_suffix in (
        ("clean", "ctd_clean.parquet"),
        ("anomalies", "ctd_anomalies.parquet"),
        ("audit", "ctd_anomaly_audit.parquet"),
    ):
        run_p = run_data_dir / f"{stem}.{stem_suffix}"
        if not run_p.is_file():
            continue
        cached = _kind_paths(cache, slug, kind)
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_p, cached)
        entry[kind] = str(cached.relative_to(project_root)).replace("\\", "/")
    entry["slug"] = slug
    entry["stem"] = stem
    entries[source_key] = entry


def build_stem_to_source_key(
    sources: list[Path], _cnv_root: Path, labels: dict[Path, str]
) -> dict[str, str]:
    """Mapa ``stem`` → clave de manifiesto (puede haber colisión; gana el último)."""
    out: dict[str, str] = {}
    for src in sources:
        out[src.stem] = labels.get(src) or src.name
    return out

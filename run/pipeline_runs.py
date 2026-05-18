"""
Utilidades puras para localizar corridas del pipeline y cargar Parquet del visor.

Sin dependencia de Streamlit: apto para tests (`pytest`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

CLEAN_PARQUET_REL = Path("data") / "perfiles_all.ctd_clean.parquet"
ANOM_PARQUET_REL = Path("data") / "perfiles_all.ctd_anomalies.parquet"
PROVENANCE_REL = Path("provenance.json")
LATEST_SENTINEL = "__latest__"


def runs_root(project_root: Path) -> Path:
    return project_root / "outputs" / "runs"


def _data_dir(run_root: Path) -> Path:
    return run_root / "data"


def _glob_clean_parts(data_dir: Path) -> list[Path]:
    if not data_dir.is_dir():
        return []
    consolidated = data_dir / CLEAN_PARQUET_REL.name
    if consolidated.is_file():
        return [consolidated]
    return sorted(data_dir.glob("*.ctd_clean.parquet"))


def has_valid_clean_artifact(run_root: Path) -> bool:
    """True si hay ``perfiles_all.ctd_clean.parquet`` o al menos un ``*.ctd_clean.parquet``."""
    return len(_glob_clean_parts(_data_dir(run_root))) > 0


def list_valid_run_roots(project_root: Path) -> list[Path]:
    """Corridas con Parquet limpio, ordenadas por ``st_mtime`` descendente."""
    rr = runs_root(project_root)
    if not rr.is_dir():
        return []
    out = [p for p in rr.iterdir() if p.is_dir() and has_valid_clean_artifact(p)]
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


def latest_valid_run_root(project_root: Path) -> Path | None:
    roots = list_valid_run_roots(project_root)
    return roots[0] if roots else None


def resolve_run_root_for_ui(project_root: Path, selection: str) -> Path | None:
    """
    ``selection`` es ``LATEST_SENTINEL`` o un ``run_id`` (nombre de carpeta bajo ``outputs/runs/``).
    """
    if selection == LATEST_SENTINEL:
        return latest_valid_run_root(project_root)
    cand = runs_root(project_root) / selection
    if has_valid_clean_artifact(cand):
        return cand
    return None


def clean_parquet_cache_token(run_root: Path) -> str:
    """Token de frescura para invalidar caché (consolidado o suma de partes)."""
    parts = _glob_clean_parts(_data_dir(run_root))
    if not parts:
        return "missing"
    total_mtime = max(p.stat().st_mtime_ns for p in parts)
    total_size = sum(p.stat().st_size for p in parts)
    return f"{total_mtime}:{total_size}:{len(parts)}"


def read_provenance_dict(run_root: Path) -> dict[str, Any] | None:
    prov = run_root / PROVENANCE_REL
    if not prov.is_file():
        return None
    try:
        return json.loads(prov.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_value_columns(df: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    cols = list(df.columns)
    col_temp = next((c for c in cols if "temp" in str(c).lower()), None)
    col_sal = next((c for c in cols if "salin" in str(c).lower() or str(c).lower() == "sal"), None)
    col_prof = next((c for c in cols if "prof" in str(c).lower()), None)
    return col_temp, col_sal, col_prof


def prepare_radial_frame(df: pd.DataFrame) -> pd.DataFrame | None:
    out = df.copy()
    out.columns = pd.Index([str(c).lower().strip() for c in out.columns])
    cols = list(out.columns)
    if "fecha" not in cols:
        return None
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
    if out["fecha"].isna().all():
        return None
    if "estacion" not in cols:
        return None
    out["estacion"] = pd.to_numeric(out["estacion"], errors="coerce")
    ct, cs, cp = _resolve_value_columns(out)
    if not all([ct, cs, cp]) or ct not in out.columns or cs not in out.columns or cp not in out.columns:
        return None
    out[cp] = pd.to_numeric(out[cp], errors="coerce")
    out[ct] = pd.to_numeric(out[ct], errors="coerce")
    out[cs] = pd.to_numeric(out[cs], errors="coerce")
    return out


def _read_clean_frame(run_root: Path) -> pd.DataFrame | None:
    parts = _glob_clean_parts(_data_dir(run_root))
    if not parts:
        return None
    if len(parts) == 1:
        return pd.read_parquet(parts[0])
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def _read_anom_frame(run_root: Path, *, columns: pd.Index) -> pd.DataFrame:
    data_dir = _data_dir(run_root)
    anom_all = data_dir / ANOM_PARQUET_REL.name
    if anom_all.is_file():
        raw = pd.read_parquet(anom_all)
        if raw.empty:
            return pd.DataFrame(columns=columns)
        prepared = prepare_radial_frame(raw)
        return prepared if prepared is not None and not prepared.empty else pd.DataFrame(columns=columns)

    parts = sorted(data_dir.glob("*.ctd_anomalies.parquet")) if data_dir.is_dir() else []
    if not parts:
        return pd.DataFrame(columns=columns)
    raw = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    if raw.empty:
        return pd.DataFrame(columns=columns)
    prepared = prepare_radial_frame(raw)
    return prepared if prepared is not None and not prepared.empty else pd.DataFrame(columns=columns)


@dataclass(frozen=True, slots=True)
class PipelineViewerLoadResult:
    df_clean: pd.DataFrame
    df_anomalies: pd.DataFrame
    df_concat_viz: pd.DataFrame
    col_temp: str
    col_sal: str
    col_prof: str
    run_root: Path
    clean_parquet: Path


def load_pipeline_viewer_data(run_root: Path) -> PipelineViewerLoadResult | None:
    """Carga limpio + anomalías desde ``run_root`` (consolidado o varios ``*.ctd_clean.parquet``)."""
    parts = _glob_clean_parts(_data_dir(run_root))
    if not parts:
        return None

    df_c = prepare_radial_frame(_read_clean_frame(run_root))
    if df_c is None:
        return None
    col_temp, col_sal, col_prof = _resolve_value_columns(df_c)
    if not all([col_temp, col_sal, col_prof]):
        return None

    df_a = _read_anom_frame(run_root, columns=df_c.columns)
    viz = pd.concat(
        [df_c.assign(_viewer_anomaly=False), df_a.assign(_viewer_anomaly=True)],
        ignore_index=True,
    )
    return PipelineViewerLoadResult(
        df_clean=df_c,
        df_anomalies=df_a,
        df_concat_viz=viz,
        col_temp=str(col_temp),
        col_sal=str(col_sal),
        col_prof=str(col_prof),
        run_root=run_root,
        clean_parquet=parts[0],
    )

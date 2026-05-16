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


def has_valid_clean_artifact(run_root: Path) -> bool:
    return (run_root / CLEAN_PARQUET_REL).is_file()


def list_valid_run_roots(project_root: Path) -> list[Path]:
    """Corridas con ``data/perfiles_all.ctd_clean.parquet``, ordenadas por ``st_mtime`` descendente."""
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
    """Token de frescura para invalidar caché si el Parquet limpio cambia."""
    p = run_root / CLEAN_PARQUET_REL
    if not p.is_file():
        return "missing"
    st = p.stat()
    return f"{st.st_mtime_ns}:{st.st_size}"


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
    """Carga limpio + anomalías desde ``run_root`` (sin caché Streamlit)."""
    clean_p = run_root / CLEAN_PARQUET_REL
    anom_p = run_root / ANOM_PARQUET_REL
    if not clean_p.is_file():
        return None
    df_c = prepare_radial_frame(pd.read_parquet(clean_p))
    if df_c is None:
        return None
    col_temp, col_sal, col_prof = _resolve_value_columns(df_c)
    if not all([col_temp, col_sal, col_prof]):
        return None
    if anom_p.is_file():
        raw_a = pd.read_parquet(anom_p)
        if raw_a.empty:
            df_a = pd.DataFrame(columns=df_c.columns)
        else:
            df_a = prepare_radial_frame(raw_a)
            if df_a is None or df_a.empty:
                df_a = pd.DataFrame(columns=df_c.columns)
    else:
        df_a = pd.DataFrame(columns=df_c.columns)
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
        clean_parquet=clean_p,
    )

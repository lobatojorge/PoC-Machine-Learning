"""
run/app.py — Visor IEO · Radiales oceánicos
==========================================

Aviso práctico
--------------
Este dashboard usa Pandas/Plotly para la UI.
El pipeline de producción (ingesta + anomalías + reportes) no depende de Pandas.

Las funciones de gráficas reutilizables (Plotly puro, sin Streamlit) viven en
`src/ieo/reports/figures_radiales.py`; este archivo solo contiene el pegamento
de Streamlit (caché, CSS, lógica de UI).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent
_SRC_DIR = (PROJECT_ROOT / "src").resolve()
_IEO_LOCAL = _SRC_DIR / "ieo"


def _bootstrap_ieo_repo_path() -> None:
    """`run/` para `cudillero_csv`; `src/` primero; quita `ieo` pip homónimo de `sys.modules`."""
    run_s = str(RUN_DIR)
    if run_s not in sys.path:
        sys.path.insert(0, run_s)
    s = str(_SRC_DIR)
    while s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)
    local_init = (_IEO_LOCAL / "__init__.py").resolve()

    def _loaded_ieo_is_local(mod: object) -> bool:
        f = getattr(mod, "__file__", None)
        if f:
            return Path(f).resolve() == local_init
        p = getattr(mod, "__path__", None)
        if p is None:
            return False
        roots = list(p) if not isinstance(p, (str, bytes)) else [p]
        want = _IEO_LOCAL.resolve()
        return any(Path(x).resolve() == want for x in roots)

    if sys.modules.get("ieo") is not None and not _loaded_ieo_is_local(sys.modules["ieo"]):
        for k in list(sys.modules):
            if k == "ieo" or k.startswith("ieo."):
                del sys.modules[k]


_bootstrap_ieo_repo_path()

from pipeline_runs import (
    LATEST_SENTINEL,
    PipelineViewerLoadResult,
    clean_parquet_cache_token,
    list_valid_run_roots,
    load_pipeline_viewer_data,
    read_provenance_dict,
    resolve_run_root_for_ui,
)
from ieo.reports.figures_radiales import (
    build_cantabrico_radials_overview_map,
    build_radial_transect_map_figure,
    parse_radial_station_coords_from_methodology,
)
from ieo.reports.radial_cnv_geo import build_radial_geo_index, stations_to_plotly_dicts

import streamlit as st

st.set_page_config(
    page_title="Radiales Cantábrico · IEO",
    layout="wide",
    page_icon=str(RUN_DIR / "assets" / "logo.webp"),
)

# ── Google Fonts + CSS global (Dark Abyss — tokens del portfolio datastur) ──
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');

/* Fuentes base */
html, body, [class*="css"], .stMarkdown, .stText, p, div, span, li {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}
code, pre, .mono, kbd {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Tokens Dark Abyss en componentes Streamlit no cubiertos por config.toml */
section[data-testid="stSidebar"] {
    background-color: #0E1626 !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
.stTabs [data-baseweb="tab-list"] {
    background-color: #080D16 !important;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background-color: #0E1626 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 6px 6px 0 0 !important;
    color: #A8BBCF !important;
    font-weight: 600;
    letter-spacing: 0.02em;
}
.stTabs [aria-selected="true"] {
    background-color: #162033 !important;
    color: #E2EAF4 !important;
    border-bottom-color: #080D16 !important;
}
/* Botones primarios → acento #00BFFF */
.stButton button[kind="primary"] {
    background-color: #00BFFF !important;
    color: #080D16 !important;
    font-weight: 700 !important;
    border: none !important;
}
.stButton button[kind="secondary"] {
    background-color: #0E1626 !important;
    color: #A8BBCF !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
}
.stButton button[kind="secondary"]:hover {
    border-color: rgba(0,191,255,0.35) !important;
    color: #E2EAF4 !important;
}
/* Expanders */
details[data-testid="stExpander"] summary {
    color: #A8BBCF !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
}
/* Evitar solapamiento del icono nativo con el contenido del expander */
details[data-testid="stExpander"] > div[data-testid="stExpanderDetails"] {
    padding-top: 10px !important;
}
/* Asegurar que Material Icons se renderice como icono, no como texto */
.material-icons {
    font-family: 'Material Icons' !important;
    font-size: 20px !important;
}
/* Texto secundario Streamlit */
.stCaption, small { color: #5B7FA3 !important; }
/* Separadores */
hr { border-color: rgba(255,255,255,0.07) !important; }
/* Ocultar botón nativo de colapso de sidebar */
[data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}
/* Ocultar barra de herramientas de Streamlit (Deploy, menú) */
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu,
header[data-testid="stHeader"] {
    display: none !important;
}
/* Eliminar padding top que Streamlit añade para la toolbar */
.stApp > header { display: none !important; }
.block-container { padding-top: 1.5rem !important; }
</style>
""",
    unsafe_allow_html=True,
)

import pandas as pd
import plotly.graph_objects as go
import markdown
import numpy as np

METODOLOGIA_RADIALES_CUDILLERO_MD = PROJECT_ROOT / "docs" / "metodologia_radiales_cudillero.md"

_radial_contract_mod: object | None = None


def _load_radial_contract_mod() -> object:
    """Import perezoso: el contrato radial solo se carga al abrir la vista (arranque más rápido)."""
    global _radial_contract_mod
    if _radial_contract_mod is not None:
        return _radial_contract_mod
    _rc_path = _SRC_DIR / "ieo" / "validation" / "radial_contract.py"
    _rc_spec = importlib.util.spec_from_file_location("_ieo_streamlit_radial_contract", _rc_path)
    if _rc_spec is None or _rc_spec.loader is None:  # pragma: no cover
        raise ImportError(f"No se pudo cargar el contrato radial desde {_rc_path}")
    _rc_mod = importlib.util.module_from_spec(_rc_spec)
    sys.modules[str(_rc_spec.name)] = _rc_mod
    _rc_spec.loader.exec_module(_rc_mod)
    _radial_contract_mod = _rc_mod
    return _rc_mod


# Metadatos de las variables del CSV: etiqueta legible y unidades para el gráfico.
# Las variables que no estén aquí usarán el nombre de columna como etiqueta y "" como unidad.
_VAR_META: dict[str, tuple[str, str]] = {
    "temperatura":        ("Temperatura",    "°C"),
    "temperatura_c":      ("Temperatura",    "°C"),
    "salinidad":          ("Salinidad",      "PSU"),
    "salinidad_psu":      ("Salinidad",      "PSU"),
    "fluorescencia":      ("Fluorescencia",  "μg/L"),
    "fluorescencia_cdom": ("Fluorescencia CDOM", "ppb"),
    "fluorescencia_afl":  ("Fluorescencia AFL",  "μg/L"),
    "par":                ("PAR",            "μE/m²/s"),
    "oxigeno":            ("Oxígeno",        "mL/L"),
    "o_100":              ("Oxígeno (100 m)","mL/L"),
    "turbidez_ntu":       ("Turbidez",       "NTU"),
    "densidad00":         ("Densidad",       "kg/m³"),
}


def _var_meta(col_name: str) -> tuple[str, str]:
    """Devuelve (var_label, var_units) para una columna, con fallback al nombre."""
    key = str(col_name).lower().strip()
    return _VAR_META.get(key, (str(col_name).replace("_", " ").title(), ""))


def _atac_allowed_for_column(col_name: str) -> bool:
    """Ahora el modelo Marcos+ATAC se aplica a cualquier variable numérica."""
    return True


# build_atac_monthly_figure y radial_contract: carga perezosa (ver render_radiales_cudillero / _render_series_and_atac).

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def load_methodology(product_id: str) -> str:
    """Lee el Markdown de metodología desde docs/ o devuelve placeholder."""
    path = PROJECT_ROOT / "docs" / f"metodologia_{product_id}.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return (
        "<p>Texto de metodología pendiente de redacción (muestreo, estaciones, instrumental). "
        f"Puede editarse en <code>docs/metodologia_{product_id}.md</code>.</p>"
    )


def _cached_cudillero_methodology_text() -> str:
    if METODOLOGIA_RADIALES_CUDILLERO_MD.exists():
        try:
            return METODOLOGIA_RADIALES_CUDILLERO_MD.read_text(encoding="utf-8")
        except OSError:
            pass
    return load_methodology("radiales_cudillero")


# parse_radial_station_coords_from_methodology y build_cudillero_radial_map_figure
# viven en src/ieo/reports/figures_radiales.py (Plotly puro, sin Streamlit).
# Se importan al inicio del archivo desde ese módulo.


def _render_pipeline_provenance_banner(
    n_clean: int,
    n_anom: int,
    fecha_min: str,
    fecha_max: str,
) -> None:
    """
    Cuatro tarjetas de proveniencia: comunican que los datos han pasado por un pipeline
    de ingesta, auditoría, QC y análisis antes de llegar al visor.
    """
    pct_clean = round(100.0 * n_clean / max(n_clean + n_anom, 1))

    _SVG_ATTRS = "width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='#00BFFF' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'"
    _SVG_ANCHOR = (
        f"<svg {_SVG_ATTRS}>"
        "<circle cx='12' cy='5' r='3'/>"
        "<line x1='12' y1='8' x2='12' y2='22'/>"
        "<path d='M5 15H2a10 10 0 0 0 20 0h-3'/>"
        "</svg>"
    )
    _SVG_CHECK = (
        f"<svg {_SVG_ATTRS}>"
        "<circle cx='12' cy='12' r='10'/>"
        "<path d='m9 12 2 2 4-4'/>"
        "</svg>"
    )
    _SVG_ALERT = (
        f"<svg {_SVG_ATTRS} stroke='#f59e0b'>"
        "<path d='m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 22h16a2 2 0 0 0 1.73-4Z'/>"
        "<line x1='12' y1='9' x2='12' y2='13'/>"
        "<line x1='12' y1='17' x2='12.01' y2='17'/>"
        "</svg>"
    )
    _SVG_ACTIVITY = (
        f"<svg {_SVG_ATTRS}>"
        "<path d='M22 12h-4l-3 9L9 3l-3 9H2'/>"
        "</svg>"
    )

    items = [
        (
            _SVG_ANCHOR,
            "Ingesta estandarizada",
            "Perfiles SeaBird `.cnv` en formato canónico. Columnas normalizadas, fechas "
            "validadas, radial identificada automáticamente (E1CU · E2CU · E3CU).",
        ),
        (
            _SVG_CHECK,
            f"Datos validados · {pct_clean}\u202f%",
            f"{n_clean:,}\u202fregistros pasan el control de calidad. "
            f"{n_anom:,}\u202fvalores atípicos quedan segregados y trazables, nunca eliminados.",
        ),
        (
            _SVG_ALERT,
            "Detección de anomalías",
            "Isolation Forest multivariante (T, S, profundidad) con semilla fija. "
            "Reproducible entre ejecuciones del pipeline.",
        ),
        (
            _SVG_ACTIVITY,
            "Análisis temporal · ATAC",
            f"Serie mensual {fecha_min}\u2013{fecha_max}. "
            "Descomposición Marcos + bandas iid sobre residuos.",
        ),
    ]
    footer_note = (
        "Los números corresponden al conjunto Parquet cargado (se actualizan al cambiar de ejecución). "
        "Visor de resultados validados · no sustituye el informe científico firmado."
    )

    parts = "".join(
        f"<div style='"
        f"border:1px solid rgba(255,255,255,0.07);"
        f"border-top:2px solid #00BFFF;"
        f"border-radius:8px;"
        f"padding:14px 16px 12px;"
        f"background:#0E1626;"
        f"display:flex;flex-direction:column;gap:8px;"
        f"'>"
        f"<div style='margin-bottom:2px;line-height:1;'>{icon}</div>"
        f"<div style='"
        f"font-size:0.65rem;"
        f"font-weight:700;"
        f"text-transform:uppercase;"
        f"letter-spacing:0.1em;"
        f"color:#5B7FA3;"
        f"'>{title}</div>"
        f"<div style='"
        f"font-size:0.74rem;"
        f"color:#A8BBCF;"
        f"line-height:1.6;"
        f"'>{body}</div>"
        f"</div>"
        for icon, title, body in items
    )
    grid_html = (
        "<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px;"
        "margin-top:10px;margin-bottom:12px;'>"
        + parts
        + "</div>"
        f"<p style='font-size:0.68rem;color:#5B7FA3;margin:0;"
        f"font-family:\"JetBrains Mono\",monospace;'>{footer_note}</p>"
    )
    st.markdown(grid_html, unsafe_allow_html=True)


def _render_data_governance_card() -> None:
    pass  # sustituida por _render_pipeline_provenance_banner (se llama con datos reales)


# ---------------------------------------------------------------------------
# Carga y validación de datos — cacheada por sesión
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Cargando Parquet de la ejecución seleccionada…")
def load_cudillero_pipeline_viewer(run_root_str: str, cache_token: str) -> PipelineViewerLoadResult | None:
    """``cache_token`` solo participa en la clave de caché de Streamlit (mtime/tamaño del Parquet limpio)."""
    _ = cache_token
    return load_pipeline_viewer_data(Path(run_root_str))


@st.cache_data(show_spinner="Indexando radiales en data/cnv/…")
def _cached_radial_geo_index(project_root_str: str, cache_token: str) -> dict:
    _ = cache_token
    idx = build_radial_geo_index(Path(project_root_str))
    return {
        "cities": [
            {
                "radial_id": c.radial_id,
                "label": c.label,
                "lat": c.lat,
                "lon": c.lon,
                "n_cnv": c.n_cnv,
            }
            for c in idx.cities
        ],
        "stations_by_radial": {
            rid: stations_to_plotly_dicts(sts)
            for rid, sts in idx.stations_by_radial.items()
        },
        "n_cnv_scanned": idx.n_cnv_scanned,
        "n_with_coords": idx.n_with_coords,
    }


def _cnv_index_cache_token(project_root: Path) -> str:
    cnv_d = project_root / "data" / "cnv"
    if not cnv_d.is_dir():
        return "missing"
    files = list(cnv_d.rglob("*.cnv"))
    if not files:
        return "empty"
    total_mtime = max(p.stat().st_mtime_ns for p in files)
    return f"{len(files)}:{total_mtime}"


@st.cache_data(show_spinner="Cargando perfiles .cnv de la radial…", ttl=3600)
def _cached_radial_cnv_dataframe(project_root_str: str, radial_id: str, cache_token: str) -> tuple[pd.DataFrame, dict]:
    _ = cache_token
    from ieo.viz.load_radial_cnv_profiles import load_radial_profiles_pandas, max_files_from_env  # noqa: PLC0415

    df, stats = load_radial_profiles_pandas(
        Path(project_root_str),
        radial_id,
        max_files=max_files_from_env(),
    )
    return df, stats


def _point_customdata_scalar(point: dict, default: str | None = None) -> str | None:
    cd = point.get("customdata")
    if cd is None:
        return default
    if isinstance(cd, (list, tuple)) and cd:
        return str(cd[0])
    if isinstance(cd, np.ndarray) and cd.size > 0:
        return str(cd.flatten()[0])
    return str(cd) if cd is not None else default


def _map_selection_points(raw_map: object) -> list:
    if raw_map is None:
        return []
    try:
        if isinstance(raw_map, dict):
            return (raw_map.get("selection") or {}).get("points", [])
        return (getattr(raw_map, "selection", None) or {}).get("points", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Hitos del investigador
# ---------------------------------------------------------------------------


def _render_investigator_highlights(res: object, var_unt: str) -> None:  # type: ignore[type-arg]
    """
    Columna derecha del layout Q&A: 5 mini-cards con hitos de la serie temporal
    calculados desde res.pipe (DataFrame) y res.meta (dict).
    """
    pipe = res.pipe  # type: ignore[attr-defined]
    meta = res.meta  # type: ignore[attr-defined]

    obs = pipe["observation"].dropna()
    is_holdout_col = pipe["is_holdout"]
    fitted_train = pipe.loc[is_holdout_col == False, "fitted"].dropna()  # noqa: E712

    # 1. Rango histórico
    if len(obs) >= 2:
        rango_stat = f"{float(obs.min()):.1f}–{float(obs.max()):.1f} {var_unt}"
        rango_body = "Rango completo de valores observados en la serie."
        rango_accent = "#00BFFF"
    else:
        rango_stat, rango_body, rango_accent = "—", "Datos insuficientes.", "#5B7FA3"

    # 2. Amplitud estacional (peak-to-trough del ajuste en entrenamiento)
    if len(fitted_train) > 12:
        amp = float(fitted_train.max() - fitted_train.min())
        amp_stat = f"Δ {amp:.1f} {var_unt}"
        amp_body = "Diferencia máx.–mín. del ciclo estacional modelado (entrenamiento)."
        amp_accent = "#00BFFF"
    else:
        amp_stat, amp_body, amp_accent = "—", "Muestra insuficiente.", "#5B7FA3"

    # 3. Tendencia lineal
    slope = meta.get("slope_c_per_year") or meta.get("trend_slope")
    if slope is None and len(fitted_train) >= 24:
        x = np.arange(len(fitted_train), dtype=float)
        slope = float(np.polyfit(x, fitted_train.to_numpy(dtype=float), 1)[0]) * 12
    if slope is not None:
        slope_f = float(slope)
        sym = "↑" if slope_f > 0 else "↓"
        trend_stat = f"{sym} {abs(slope_f):.3f} {var_unt}/año"
        trend_body = "Pendiente lineal estimada del ajuste (período de entrenamiento)."
        trend_accent = "#f59e0b" if abs(slope_f) > 0.05 else "#22c55e"
    else:
        trend_stat, trend_body, trend_accent = "—", "No disponible.", "#5B7FA3"

    # 4. Observaciones del holdout fuera de la banda 95 %
    holdout_obs = pipe.loc[(is_holdout_col == True) & pipe["observation"].notna()]  # noqa: E712
    n_holdout = len(holdout_obs)
    n_out = 0
    if n_holdout > 0 and "temp_fc_lo_95" in pipe.columns and "temp_fc_hi_95" in pipe.columns:
        out_mask = (holdout_obs["observation"] < holdout_obs["temp_fc_lo_95"]) | (
            holdout_obs["observation"] > holdout_obs["temp_fc_hi_95"]
        )
        n_out = int(out_mask.sum())
    pct_out = round(100 * n_out / max(n_holdout, 1)) if n_holdout > 0 else 0
    out_accent = "#22c55e" if pct_out == 0 else "#f59e0b" if pct_out < 30 else "#ef4444"
    out_stat = f"{n_out} / {n_holdout}" if n_holdout > 0 else "—"
    _holdout_label = f"últimos {n_holdout} meses" if n_holdout > 0 else "validación"
    out_body = (
        f"{pct_out}\u202f% fuera de la banda 95\u202f% en los {_holdout_label}."
        if n_holdout > 0
        else "Sin período de validación disponible."
    )

    # 5. Dato más reciente
    last_obs_rows = pipe.loc[pipe["observation"].notna()]
    if len(last_obs_rows) > 0:
        last_row = last_obs_rows.iloc[-1]
        last_val = float(last_row["observation"])
        last_date = pd.to_datetime(last_row["fecha"]).strftime("%b %Y")
        last_stat = f"{last_val:.2f} {var_unt}"
        last_body = f"Última observación registrada: {last_date}."
        last_accent = "#1a9aff"
    else:
        last_stat, last_body, last_accent = "—", "Sin datos.", "#5B7FA3"

    # SVG icons (18 px, stroke-only)
    _s = (
        "width='18' height='18' viewBox='0 0 24 24' fill='none' "
        "stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'"
    )
    _icon_range = f"<svg {_s}><line x1='3' y1='6' x2='21' y2='6'/><line x1='3' y1='12' x2='21' y2='12'/><line x1='3' y1='18' x2='21' y2='18'/></svg>"
    _icon_wave = f"<svg {_s}><path d='M2 12c2-4 4-4 6 0s4 4 6 0 4-4 6 0'/></svg>"
    _icon_trend = f"<svg {_s}><polyline points='22 7 13.5 15.5 8.5 10.5 2 17'/><polyline points='16 7 22 7 22 13'/></svg>"
    _icon_band = f"<svg {_s}><circle cx='12' cy='12' r='10'/><line x1='12' y1='8' x2='12' y2='12'/><line x1='12' y1='16' x2='12.01' y2='16'/></svg>"
    _icon_last = f"<svg {_s}><circle cx='12' cy='12' r='1'/><path d='M20.2 20.2c2.04-2.03.02-7.36-4.5-11.9C11.2 3.8 5.9 1.8 3.8 3.8-2.04 5.83 7.98 15.36 8 15.9'/></svg>"

    def _hi_card(icon: str, label: str, stat: str, body: str, accent: str) -> str:
        return (
            f"<div style='background:#0A1220;border-radius:10px;padding:12px 14px;"
            f"border-top:2px solid {accent};'>"
            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:4px;'>"
            f"<span style='color:{accent};line-height:1;'>{icon}</span>"
            f"<span style='font-size:0.57rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.12em;color:#5B7FA3;'>{label}</span>"
            f"</div>"
            f"<div style='font-family:\"JetBrains Mono\",monospace;font-size:0.92rem;"
            f"font-weight:700;color:{accent};margin-bottom:3px;'>{stat}</div>"
            f"<div style='font-size:0.67rem;color:#A8BBCF;line-height:1.45;'>{body}</div>"
            f"</div>"
        )

    cards = (
        _hi_card(_icon_range, "Rango histórico", rango_stat, rango_body, rango_accent)
        + _hi_card(_icon_wave, "Amplitud estacional", amp_stat, amp_body, amp_accent)
        + _hi_card(_icon_trend, "Tendencia", trend_stat, trend_body, trend_accent)
        + _hi_card(_icon_band, "Pronóstico vs obs.", out_stat, out_body, out_accent)
        + _hi_card(_icon_last, "Último dato", last_stat, last_body, last_accent)
    )
    st.markdown(
        "<p style='font-size:0.65rem;font-family:\"JetBrains Mono\",monospace;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;"
        "margin:20px 0 10px;border-top:1px solid rgba(255,255,255,0.07);padding-top:16px;'>"
        "Hitos de la serie</p>"
        f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;'>"
        + cards
        + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Agregando serie mensual por profundidad…")
def _monthly_value_at_depth(
    df: pd.DataFrame,
    col_fecha: str,
    col_prof: str,
    col_value: str,
    col_estacion: str,
    target_depth_m: float,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    from ieo.reports.monthly_at_depth import monthly_value_at_depth  # noqa: PLC0415

    return monthly_value_at_depth(
        df,
        col_fecha=col_fecha,
        col_prof=col_prof,
        col_value=col_value,
        col_estacion=col_estacion,
        target_depth_m=target_depth_m,
    )


def render_radiales_explorer() -> None:
    """Hub Radiales: localidad (mapa) → estación → series Marcos+ATAC."""

    if "radial_id" not in st.session_state:
        st.session_state["radial_id"] = None
    if "estacion_seleccionada_csv" not in st.session_state:
        st.session_state["estacion_seleccionada_csv"] = 1

    _rc = _load_radial_contract_mod()
    _bootstrap_ieo_repo_path()
    from ieo.radiales_catalog import RADIAL_ID_CUDILLERO, filter_dataframe_to_radial  # noqa: PLC0415

    geo = _cached_radial_geo_index(
        str(PROJECT_ROOT.resolve()),
        _cnv_index_cache_token(PROJECT_ROOT),
    )
    cities: list[dict] = geo.get("cities", [])
    stations_by_radial: dict[str, list] = geo.get("stations_by_radial", {})

    st.markdown(
        """
<div style="background:linear-gradient(135deg,#0E1626 0%,#080D16 100%);
border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:28px 32px 20px;margin-bottom:16px;">
  <span style="display:inline-flex;padding:4px 10px;border-radius:9999px;
border:1px solid rgba(0,191,255,0.25);background:rgba(0,191,255,0.08);
font-family:'JetBrains Mono',monospace;font-size:0.65rem;font-weight:700;
text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;margin-bottom:14px;">
Radiales · Cantábrico</span>
  <h1 style="font-family:'Plus Jakarta Sans',sans-serif;font-size:2rem;font-weight:800;
color:#E2EAF4;margin:0 0 6px;">Radiales oceánicas</h1>
  <p style="font-size:0.88rem;color:#A8BBCF;margin:0;">
    Elige localidad en el mapa · luego estación · visualiza temperatura y salinidad a 5&nbsp;m
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    if not cities:
        st.warning("No hay radiales con coordenadas en `data/cnv/`. Coloca ficheros `.cnv` y recarga.")
        st.stop()

    st.markdown(
        "<p style='font-size:0.65rem;font-family:\"JetBrains Mono\",monospace;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;margin:12px 0 8px;'>"
        "1 · Localidad</p>",
        unsafe_allow_html=True,
    )

    city_labels = {c["radial_id"]: str(c["label"]) for c in cities}
    city_options = [c["radial_id"] for c in cities]
    prev_radial = st.session_state.get("radial_id")

    with st.sidebar:
        st.markdown("### Radial")
        pick = st.selectbox(
            "Localidad",
            options=[""] + city_options,
            format_func=lambda x: "— elige —" if not x else city_labels.get(x, x),
            index=(city_options.index(prev_radial) + 1) if prev_radial in city_options else 0,
            key="sidebar_radial_pick",
        )
        if pick and pick != prev_radial:
            st.session_state["radial_id"] = pick
            st.session_state.pop("station_tab_temp", None)
            st.session_state.pop("station_tab_sal", None)

    fig_overview = build_cantabrico_radials_overview_map(
        cities,
        selected_radial_id=st.session_state.get("radial_id"),
    )
    st.caption("Haz clic en una localidad del mapa (o elige en la barra lateral).")
    st.plotly_chart(
        fig_overview,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="radial_overview_map",
        config={"displayModeBar": False},
    )

    for pt in _map_selection_points(st.session_state.get("radial_overview_map")):
        rid = _point_customdata_scalar(pt)
        if rid and rid in city_labels:
            if st.session_state.get("radial_id") != rid:
                st.session_state["radial_id"] = rid
                st.session_state.pop("station_tab_temp", None)
                st.session_state.pop("station_tab_sal", None)
            break

    radial_id = st.session_state.get("radial_id")
    if not radial_id or radial_id not in city_labels:
        st.info("Selecciona **Cudillero**, **Gijón**, **Santander** o **A Coruña** en el mapa.")
        st.stop()

    radial_label = city_labels[radial_id]
    pipe: PipelineViewerLoadResult | None = None
    cnv_stats: dict = {}
    data_source = "cnv"

    if radial_id == RADIAL_ID_CUDILLERO:
        run_root = resolve_run_root_for_ui(
            PROJECT_ROOT,
            st.session_state.get("pipeline_run_select", LATEST_SENTINEL),
        )
        if run_root is not None:
            cache_tok = clean_parquet_cache_token(run_root)
            pipe = load_cudillero_pipeline_viewer(str(run_root.resolve()), cache_tok)

    if pipe is not None and radial_id == RADIAL_ID_CUDILLERO:
        df_c, n_other_radial = filter_dataframe_to_radial(pipe.df_clean, RADIAL_ID_CUDILLERO)
        if n_other_radial > 0:
            st.warning(
                f"Se excluyeron **{n_other_radial:,}** filas de otras radiales en el Parquet."
            )
        col_temp, col_sal, col_prof = pipe.col_temp, pipe.col_sal, pipe.col_prof
        data_source = "pipeline"
        n_anom_banner = len(pipe.df_anomalies)
        n_clean_banner = len(pipe.df_clean)
    else:
        df_c, cnv_stats = _cached_radial_cnv_dataframe(
            str(PROJECT_ROOT.resolve()),
            radial_id,
            _cnv_index_cache_token(PROJECT_ROOT),
        )
        if radial_id == RADIAL_ID_CUDILLERO and pipe is None:
            st.caption(
                "Cudillero: lectura directa de `.cnv` (sin Parquet). "
                "Ejecuta `python run/main.py` para anomalías."
            )
        col_temp = next((c for c in df_c.columns if "temp" in str(c).lower()), "temperatura_c")
        col_sal = next(
            (c for c in df_c.columns if "salin" in str(c).lower() or str(c).lower() == "sal"),
            "salinidad_psu",
        )
        col_prof = next((c for c in df_c.columns if "prof" in str(c).lower()), "profundidad_m")
        n_anom_banner = 0
        n_clean_banner = len(df_c)

    if df_c is None or df_c.empty:
        st.error(
            f"No hay perfiles CTD para **{radial_label}**. "
            f"En disco: {cnv_stats.get('n_radial_clasificados', '—')} `.cnv` clasificados."
        )
        st.stop()

    md_method = ""
    stations_geo = list(stations_by_radial.get(radial_id, []))
    if radial_id == RADIAL_ID_CUDILLERO:
        md_method = _cached_cudillero_methodology_text()
        md_stations = parse_radial_station_coords_from_methodology(md_method)
        if md_stations:
            stations_geo = md_stations

    _est_vals = sorted(df_c["estacion"].dropna().unique().astype(int).tolist())
    if _est_vals and radial_id == RADIAL_ID_CUDILLERO and not all(e in (1, 2, 3) for e in _est_vals):
        st.info(
            "Estaciones SeaBird (`** Station:`): "
            f"{_est_vals[:10]}{'…' if len(_est_vals) > 10 else ''}."
        )

    _fc = df_c["fecha"].dropna()
    _fecha_min_y = str(_fc.min().year) if len(_fc) else "—"
    _fecha_max_y = str(_fc.max().year) if len(_fc) else "—"
    _ultima_campana = _fc.max().strftime("%d/%m/%Y") if len(_fc) else "—"

    st.markdown(
        "<p style='font-size:0.65rem;font-family:\"JetBrains Mono\",monospace;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;margin:16px 0 8px;'>"
        f"2 · {radial_label} · 3 · Estación y series</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div style="background:linear-gradient(135deg,#0E1626 0%,#080D16 100%);
border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:22px 28px 18px;margin-bottom:16px;">
  <h2 style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1.35rem;font-weight:800;
color:#E2EAF4;margin:0 0 8px;">{radial_label}</h2>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <span style="padding:4px 12px;border-radius:9999px;background:rgba(255,255,255,0.05);
border:1px solid rgba(255,255,255,0.1);font-size:0.72rem;color:#A8BBCF;
font-family:'JetBrains Mono',monospace;">Cobertura <strong style="color:#E2EAF4;">{_fecha_min_y}–{_fecha_max_y}</strong></span>
    <span style="padding:4px 12px;border-radius:9999px;background:rgba(255,255,255,0.05);
border:1px solid rgba(255,255,255,0.1);font-size:0.72rem;color:#A8BBCF;
font-family:'JetBrains Mono',monospace;">Última <strong style="color:#E2EAF4;">{_ultima_campana}</strong></span>
    <span style="padding:4px 12px;border-radius:9999px;background:rgba(255,255,255,0.05);
border:1px solid rgba(255,255,255,0.1);font-size:0.72rem;color:#A8BBCF;
font-family:'JetBrains Mono',monospace;">Fuente <strong style="color:#E2EAF4;">{data_source}</strong></span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


    if data_source == "pipeline" and pipe is not None:
        _render_pipeline_provenance_banner(
            n_clean=n_clean_banner,
            n_anom=n_anom_banner,
            fecha_min=str(_fc.min().date()) if len(_fc) else "—",
            fecha_max=str(_fc.max().date()) if len(_fc) else "—",
        )
    else:
        st.caption(
            f"**{cnv_stats.get('n_perfiles_cargados', '—')}** perfiles `.cnv` cargados "
            f"({cnv_stats.get('n_radial_clasificados', '—')} clasificados en disco)."
        )

    depth_m = 5.0

    ids_map = [int(s["estacion"]) for s in stations_geo] if stations_geo else []
    ids_data = sorted({int(float(x)) for x in df_c["estacion"].dropna().unique().tolist()})
    opts = sorted(set(ids_map) & set(ids_data)) or ids_data or ids_map
    if not opts:
        st.warning("No hay estaciones con datos en esta radial.")
        st.stop()
    name_by_id = {int(s["estacion"]): str(s["nombre"]) for s in stations_geo}
    for e in opts:
        name_by_id.setdefault(int(e), f"Estación {int(e)}")

    _map_key = f"radial_transect_map_{radial_id}"
    for pt in _map_selection_points(st.session_state.get(_map_key)):
        est_val = _point_customdata_scalar(pt)
        if est_val is not None and str(est_val).strip() != "":
            clicked = int(float(est_val))
            if clicked in opts:
                st.session_state["station_tab_temp"] = clicked
                st.session_state["station_tab_sal"] = clicked
            break


    def _axis_label_for_value_column(col: str) -> str:
        c = str(col).lower()
        if "temp" in c or c in ("temperatura", "temperatura_c"):
            return "T (°C)"
        if "salin" in c or c in ("sal", "salinidad_psu"):
            return "S (PSU)"
        if "fluor" in c or "cdom" in c or "afl" in c:
            return str(col)
        if "clor" in c:
            return str(col)
        if "par" in c:
            return str(col)
        if "ox" in c or "o2" in c or "o_100" in c:
            return str(col)
        if "turb" in c:
            return str(col)
        if "dens" in c or "density" in c:
            return str(col)
        if "cstar" in c or "at0" in c or "tr0" in c:
            return str(col)
        return str(col)

    def _render_series_and_atac(
        *,
        df_gijon: pd.DataFrame | None,
        source_label: str,
        col_prof: str | None = None,
        col_temp: str | None = None,
        col_value: str | None = None,
        target_depth_m: float = 5.0,
        col_estacion: str = "estacion",
        col_fecha: str = "fecha",
        fixed_station: int,
        widget_key_suffix: str = "",
    ) -> None:
        if df_gijon is None or df_gijon.empty:
            st.warning(
                "No hay datos listos para graficar: revisa el **conjunto de datos** seleccionado en la barra lateral "
                "(ejecución del pipeline)."
            )
            return

        # Resolver columnas en CSV legacy si no se pasan explícitas
        if col_prof is None:
            col_prof = next((str(c) for c in df_gijon.columns if "prof" in str(c).lower()), None)
        if col_temp is None:
            col_temp = next((str(c) for c in df_gijon.columns if "temp" in str(c).lower()), None)

        col_value_resolved = col_value if col_value is not None else col_temp

        # Comprobaciones mínimas
        if col_estacion not in df_gijon.columns or col_fecha not in df_gijon.columns:
            st.warning(f"[{source_label}] Faltan columnas requeridas: `{col_estacion}` y/o `{col_fecha}`.")
            return
        if col_prof is None or col_value_resolved is None or str(col_value_resolved) not in df_gijon.columns:
            st.warning(
                f"[{source_label}] No se encuentran columnas de profundidad/valor en: {list(df_gijon.columns)}"
            )
            return

        df_monthly, diag_interp = _monthly_value_at_depth(
            df_gijon,
            col_fecha=col_fecha,
            col_prof=col_prof,
            col_value=str(col_value_resolved),
            col_estacion=col_estacion,
            target_depth_m=float(target_depth_m),
        )
        if df_monthly.empty:
            st.warning(
                f"[{source_label}] No hay datos suficientes para la serie mensual a **{target_depth_m:g} m** "
                f"(`{col_value_resolved}`)."
            )
            return

        # --- Contrato de datos radial (QC físico + serie mensual; antes de cualquier modelo) ---
        vk = _rc.infer_variable_kind(str(col_value_resolved))
        if "acronimo" in df_gijon.columns:
            cast_keys_t: tuple[str, ...] = ("acronimo", col_estacion)
            profile_df = df_gijon
        elif "cast" in df_gijon.columns:
            cast_keys_t = ("cast", col_estacion)
            profile_df = df_gijon
        else:
            profile_df = df_gijon.copy()
            profile_df["_perf_day"] = pd.to_datetime(profile_df[col_fecha], errors="coerce").dt.normalize()
            cast_keys_t = ("_perf_day", col_estacion)

        violations: list = []
        if vk in ("temperature", "salinity"):
            if vk == "temperature":
                chk = profile_df.copy()
                if str(col_value_resolved) != "temperatura_c":
                    chk = chk.rename(columns={str(col_value_resolved): "temperatura_c"})
                if str(col_prof) != "profundidad_m":
                    chk = chk.rename(columns={str(col_prof): "profundidad_m"})
                need = ["fecha", "estacion", "profundidad_m", "temperatura_c"]
                if all(c in chk.columns for c in need):
                    try:
                        import polars as pl  # noqa: PLC0415

                        ex = [c for c in ("cast", "acronimo") if c in chk.columns]
                        violations.extend(
                            _rc.validate_canonical_ctd_polars(pl.from_pandas(chk[need + ex].copy()))
                        )
                    except Exception:
                        violations.extend(
                            _rc.validate_profile_dataframe(
                                profile_df,
                                col_prof=str(col_prof),
                                col_value=str(col_value_resolved),
                                col_estacion=col_estacion,
                                cast_keys=cast_keys_t,
                                variable_kind="temperature",
                            )
                        )
                else:
                    violations.extend(
                        _rc.validate_profile_dataframe(
                            profile_df,
                            col_prof=str(col_prof),
                            col_value=str(col_value_resolved),
                            col_estacion=col_estacion,
                            cast_keys=cast_keys_t,
                            variable_kind="temperature",
                        )
                    )
            else:
                violations.extend(
                    _rc.validate_profile_dataframe(
                        profile_df,
                        col_prof=str(col_prof),
                        col_value=str(col_value_resolved),
                        col_estacion=col_estacion,
                        cast_keys=cast_keys_t,
                        variable_kind="salinity",
                    )
                )
            violations.extend(
                _rc.validate_monthly_radial_series(
                    df_monthly,
                    col_fecha="fecha",
                    col_val="valor_prof",
                    col_estacion=col_estacion,
                    variable_kind=vk,
                )
            )

        errs = [v for v in violations if v.severity == _rc.ViolationSeverity.ERROR]
        warns = [v for v in violations if v.severity == _rc.ViolationSeverity.WARNING]

        if errs:
            st.error(
                "**Contrato de datos radial:** se han detectado incumplimientos **ERROR**. "
                "El gráfico no se muestra por defecto hasta revisión (datos no auditados)."
            )
            st.markdown(_rc.format_violations_markdown(errs))
            unlock = st.checkbox(
                "Solo diagnóstico interno: mostrar gráfico pese a errores del contrato",
                value=False,
                key=f"contract_unlock_err_{source_label}_{col_value_resolved}_{target_depth_m}{widget_key_suffix}",
            )
            if not unlock:
                return

        selected = int(fixed_station)
        df_station = df_monthly[df_monthly[col_estacion] == int(selected)].copy()
        df_station["fecha"] = pd.to_datetime(df_station["fecha"], errors="coerce")
        df_station["valor_prof"] = pd.to_numeric(df_station["valor_prof"], errors="coerce")
        df_station = df_station.dropna(subset=["fecha", "valor_prof"]).sort_values("fecha")
        if df_station.empty:
            st.warning(f"[{source_label}] No hay serie mensual válida para esta estación.")
            return

        n_obs_months = float(df_station["fecha"].dt.to_period("M").nunique())

        if n_obs_months < 2:
            st.info(
                f"No se calcula **Marcos+ATAC** porque hay pocos meses observados (n={int(n_obs_months)}). "
                "Añade campañas en meses distintos para activar el ajuste."
            )
            return

        var_lbl, var_unt = _var_meta(str(col_value_resolved))
        depth_lbl = int(target_depth_m) if float(target_depth_m).is_integer() else target_depth_m
        _est_name = name_by_id.get(int(selected), f"Estación {int(selected)}")
        st.subheader(f"{_est_name}")
        try:
            import importlib  # noqa: PLC0415
            import atac_monthly_report as _atac_mod  # noqa: PLC0415
            importlib.reload(_atac_mod)
            build_atac_monthly_figure = _atac_mod.build_atac_monthly_figure

            monthly_for_atac = df_station[["fecha", "valor_prof"]].rename(columns={"valor_prof": "temp_5m"})
            res = build_atac_monthly_figure(
                project_root=PROJECT_ROOT,
                monthly_5m=monthly_for_atac,
                station_label=_est_name,
                holdout_months=12,
                var_label=var_lbl,
                var_units=var_unt,
                depth_m=int(target_depth_m),
            )
        except Exception as exc:
            st.warning(
                f"No se pudo generar la figura Marcos+ATAC para **{var_lbl}**. "
                f"Motivo: `{type(exc).__name__}: {exc}`\n\n"
                f"Meses observados: **{int(n_obs_months)}**; rango: **{df_station['fecha'].min().date()} → {df_station['fecha'].max().date()}**."
            )
            return

        # ── Tarjetones de calidad de datos (encima de la gráfica) ──────────────
        _n_casts = diag_interp["n_casts"]
        _n_valid = diag_interp["n_casts_con_valor"]
        _pct_prof = round(100 * _n_valid / max(_n_casts, 1))

        # Cobertura mensual: meses observados vs meses en el calendario de la serie
        _fecha_min_st = df_station["fecha"].min()
        _fecha_max_st = df_station["fecha"].max()
        _total_months = int(
            (_fecha_max_st.year - _fecha_min_st.year) * 12
            + (_fecha_max_st.month - _fecha_min_st.month)
            + 1
        )
        _pct_months = round(100 * int(n_obs_months) / max(_total_months, 1))

        def _card_accent(pct: int) -> str:
            if pct >= 75:
                return "#10b981"  # verde
            if pct >= 45:
                return "#f59e0b"  # ámbar
            return "#ef4444"     # rojo

        _gap_label = res.gap_summary if res.gap_summary else "Sin huecos significativos."
        _gap_accent = "#10b981" if not res.gap_summary else "#f59e0b"
        _ultima = df_station["fecha"].max().strftime("%b %Y")

        def _metric_card(stat: str, label: str, body: str, accent: str) -> str:
            return (
                f"<div style='border:1px solid rgba(255,255,255,0.07);border-top:3px solid {accent};"
                f"border-radius:8px;padding:14px 16px 12px;background:#0E1626;'>"
                f"<div style='font-family:\"JetBrains Mono\",monospace;font-size:1.2rem;font-weight:700;"
                f"color:{accent};margin-bottom:3px;'>{stat}</div>"
                f"<div style='font-size:0.63rem;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:0.1em;color:#5B7FA3;margin-bottom:6px;'>{label}</div>"
                f"<div style='font-size:0.72rem;color:#A8BBCF;line-height:1.5;'>{body}</div>"
                f"</div>"
            )

        _quality_cards = (
            _metric_card(
                f"{_pct_months}\u202f%",
                "Cobertura mensual",
                f"{int(n_obs_months)} de {_total_months} meses con observación "
                f"({_fecha_min_st.strftime('%Y')}–{_fecha_max_st.strftime('%Y')})",
                _card_accent(_pct_months),
            )
            + _metric_card(
                f"{_pct_prof}\u202f%",
                f"Perfiles válidos a {depth_lbl} m",
                f"{_n_valid} de {_n_casts} lances alcanzan la profundidad objetivo. "
                f"{diag_interp['n_casts_sin_cobertura_en_profundidad']} sin cobertura.",
                _card_accent(_pct_prof),
            )
            + _metric_card(
                _ultima,
                "Última campaña",
                "Fecha del muestreo más reciente incluido en esta serie.",
                "#1a9aff",
            )
            + _metric_card(
                str(len([s for s in res.gap_summary.split(";") if s.strip()])) if res.gap_summary else "0",
                "Períodos sin dato",
                _gap_label,
                _gap_accent,
            )
        )
        st.markdown(
            "<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;'>"
            + _quality_cards
            + "</div>",
            unsafe_allow_html=True,
        )

        st.plotly_chart(res.fig, use_container_width=True)

        # Hitos del investigador en horizontal
        _render_investigator_highlights(res, var_unt)

        # Acordeón FAQ
        _pairs = [s.split("|||", 1) for s in res.footer_md.split("\n\n---\n\n") if "|||" in s]
        _qa_style = (
            "<style>"
            "details.ieo-qa{"
            "  border:1px solid rgba(255,255,255,0.07);"
            "  border-radius:8px;"
            "  margin-bottom:5px;"
            "  background:#0E1626;"
            "  overflow:hidden;"
            "}"
            "details.ieo-qa[open]{"
            "  border-left:3px solid #00BFFF;"
            "  border-radius:0 8px 8px 0;"
            "}"
            "details.ieo-qa summary{"
            "  cursor:pointer;"
            "  padding:9px 12px;"
            "  font-size:0.76rem;"
            "  font-weight:600;"
            "  color:#A8BBCF;"
            "  list-style:none;"
            "  display:flex;"
            "  justify-content:space-between;"
            "  align-items:center;"
            "  user-select:none;"
            "}"
            "details.ieo-qa[open] summary{color:#E2EAF4;}"
            "details.ieo-qa summary::-webkit-details-marker{display:none;}"
            ".ieo-qa-chevron{font-size:0.7rem;color:#5B7FA3;transition:transform 0.15s;}"
            "details.ieo-qa[open] .ieo-qa-chevron{transform:rotate(180deg);color:#00BFFF;}"
            ".ieo-qa-body{"
            "  padding:2px 12px 10px;"
            "  font-size:0.73rem;"
            "  color:#A8BBCF;"
            "  line-height:1.65;"
            "}"
            "</style>"
        )
        if _pairs:
            _items = "".join(
                f"<details class='ieo-qa'>"
                f"<summary>{q.strip()}<span class='ieo-qa-chevron'>▾</span></summary>"
                f"<div class='ieo-qa-body'>{a.strip()}</div>"
                f"</details>"
                for q, a in _pairs
            )
            st.markdown(
                _qa_style
                + "<p style='font-size:0.65rem;font-family:\"JetBrains Mono\",monospace;font-weight:700;"
                "text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;"
                "margin:16px 0 8px;'>"
                "Preguntas sobre esta gráfica</p>"
                + _items,
                unsafe_allow_html=True,
            )

        if warns:
            _warn_svg = (
                "<svg width='16' height='16' viewBox='0 0 24 24' fill='none' "
                "stroke='#f59e0b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
                "<path d='m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 22h16a2 2 0 0 0 1.73-4Z'/>"
                "<line x1='12' y1='9' x2='12' y2='13'/>"
                "<line x1='12' y1='17' x2='12.01' y2='17'/>"
                "</svg>"
            )
            _warn_items = "".join(
                f"<li style='margin-bottom:4px;'>{_rc.format_contract_warning_postchart(w)}</li>"
                for w in warns
            )
            st.markdown(
                f"<div style='background:#1a1200;border:1px solid rgba(245,158,11,0.25);"
                f"border-left:3px solid #f59e0b;border-radius:8px;padding:12px 16px;margin-top:12px;'>"
                f"<div style='display:flex;align-items:center;gap:7px;margin-bottom:6px;'>"
                f"{_warn_svg}"
                f"<span style='font-size:0.63rem;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:0.1em;color:#f59e0b;'>Notas automáticas de calidad</span>"
                f"</div>"
                f"<ul style='margin:0;padding-left:16px;font-size:0.74rem;color:#A8BBCF;line-height:1.6;'>"
                f"{_warn_items}"
                f"</ul>"
                f"<p style='margin:8px 0 0;font-size:0.62rem;color:#5B7FA3;'>No bloquean la visualización · "
                f"contexto estadístico, no error de medición.</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Pestañas — primer elemento visual tras la cabecera ───────────────────
    st.markdown(
        "<p style='font-size:0.65rem;font-family:\"JetBrains Mono\",monospace;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;margin:20px 0 8px;'>"
        "Explorar datos</p>",
        unsafe_allow_html=True,
    )
    tab_temp, tab_sal = st.tabs(["Temperatura", "Salinidad"])

    def _station_buttons(tab_key: str) -> int | None:
        """Renderiza tres botones de estación y devuelve la seleccionada (o None)."""
        current = st.session_state.get(tab_key)
        btn_labels = [name_by_id.get(o, f"Estación {o}") for o in opts]
        pad = max(0, 4 - len(opts))
        bcols = st.columns(len(opts) + pad, gap="small")
        for i, (opt, lbl) in enumerate(zip(opts, btn_labels)):
            is_active = current == opt
            if bcols[i].button(
                lbl,
                key=f"btn_{tab_key}_{opt}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state[tab_key] = opt
                st.rerun()
        return st.session_state.get(tab_key)

    def _depth_buttons(suffix: str) -> None:
        """Fila de profundidades: 5 m activa, resto deshabilitadas (próximamente)."""
        depth_opts = [5, 20, 50]
        pad = max(0, 7 - len(depth_opts))
        dcols = st.columns(len(depth_opts) + pad, gap="small")
        for i, d in enumerate(depth_opts):
            available = d == 5
            dcols[i].button(
                f"{d} m",
                key=f"btn_depth_{suffix}_{d}",
                type="primary" if available else "secondary",
                disabled=not available,
                help=None if available else "Próximamente disponible",
                use_container_width=True,
            )

    with tab_temp:
        sel_temp = _station_buttons("station_tab_temp")
        st.markdown(
            "<p style='font-size:0.63rem;font-family:\"JetBrains Mono\",monospace;"
            "text-transform:uppercase;letter-spacing:0.1em;color:#5B7FA3;margin:6px 0 2px 0;'>Profundidad</p>",
            unsafe_allow_html=True,
        )
        _depth_buttons("temp")
        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        if sel_temp is None:
            st.markdown(
                "<div style='text-align:center;color:#5B7FA3;padding:60px 0;font-size:0.85rem;"
                "font-family:\"JetBrains Mono\",monospace;letter-spacing:0.04em;'>"
                "Selecciona una estación para ver la serie temporal."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            _render_series_and_atac(
                df_gijon=df_c,
                source_label=data_source,
                col_prof=col_prof,
                col_temp=col_temp,
                col_value=col_temp,
                target_depth_m=depth_m,
                fixed_station=int(sel_temp),
            )

    with tab_sal:
        sel_sal = _station_buttons("station_tab_sal")
        st.markdown(
            "<p style='font-size:0.63rem;font-family:\"JetBrains Mono\",monospace;"
            "text-transform:uppercase;letter-spacing:0.1em;color:#5B7FA3;margin:6px 0 2px 0;'>Profundidad</p>",
            unsafe_allow_html=True,
        )
        _depth_buttons("sal")
        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        if sel_sal is None:
            st.markdown(
                "<div style='text-align:center;color:#5B7FA3;padding:60px 0;font-size:0.85rem;"
                "font-family:\"JetBrains Mono\",monospace;letter-spacing:0.04em;'>"
                "Selecciona una estación para ver la serie temporal."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            _render_series_and_atac(
                df_gijon=df_c,
                source_label=data_source,
                col_prof=col_prof,
                col_temp=col_temp,
                col_value=col_sal,
                target_depth_m=depth_m,
                fixed_station=int(sel_sal),
                widget_key_suffix="_sal",
            )

    # ── Transecto — mapa y contexto metodológico al final ────────────────────
    st.markdown("---")
    st.markdown(
        "<p style='font-size:0.65rem;font-family:\"JetBrains Mono\",monospace;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;margin:0 0 10px 0;'>"
        "Transecto · ubicación de las estaciones</p>",
        unsafe_allow_html=True,
    )
    col_map, col_txt = st.columns([1, 1], gap="large")

    with col_map:
        st.caption("Haz clic en una estación del mapa para seleccionarla en las pestañas de arriba.")
        if not stations_geo:
            st.info(
                "Coordenadas no disponibles. Añade `<!-- E1 lat lon | … -->` al final de "
                "`docs/metodologia_radiales_cudillero.md` para activar el mapa."
            )
        fig_map = build_cudillero_radial_map_figure(stations_geo)
        st.plotly_chart(
            fig_map,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="cud_mapbox",
            config={"displayModeBar": False},
        )

    with col_txt:
        st.markdown("#### Metodología")
        st.caption("Perfiles CTD mensuales sobre la plataforma cantábrica, transecto perpendicular a la costa.")
        md_display = re.sub(r"<!--.*?-->", "", md_method, flags=re.DOTALL).strip()
        html_method = markdown.markdown(md_display, extensions=["extra", "sane_lists"])
        st.markdown(
            f"<div style='max-height:400px;overflow-y:auto;padding-right:8px;"
            f"font-size:0.86em;line-height:1.6;color:#A8BBCF;'>{html_method}</div>",
            unsafe_allow_html=True,
        )


def main() -> None:
    # Una vez por sesión de navegador: diario legible de arranque (no en cada interacción).
    if "_public_run_journal_written" not in st.session_state:
        st.session_state["_public_run_journal_written"] = True
        try:
            _bootstrap_ieo_repo_path()
            from ieo.observability.session_audit import append_public_run_journal_entry  # noqa: PLC0415

            append_public_run_journal_entry(PROJECT_ROOT, kind="streamlit_dashboard_boot")
        except Exception:
            pass

    render_radiales_explorer()


if __name__ == "__main__":
    main()


"""
app.py — Visor IEO · Radiales oceánicos
=========================================
Punto de entrada de la aplicación Streamlit.

Convenciones
------------
- Los imports de visualización se hacen desde ``src.visualization``,
  que actúa de fachada sobre ``src/03_visualization.py``.
- ``load_and_validate_gijon`` está decorada con ``@st.cache_data`` para
  que el CSV se lea una sola vez por sesión y no en cada rerun.
- Cada función ``render_*`` es pura: recibe datos y devuelve None
  (efectos de lado exclusivamente en la UI de Streamlit).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import markdown
import numpy as np

# Garantiza que el paquete src/ es importable aunque el CWD no sea la raíz
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.visualization import (  # noqa: E402
    plot_hovmoller_termoclina,
    plot_temp_5m_anual,
    plot_temp_5m_anual_estaciones_con_ic_global,
    plot_wginor_anomaly,
    plot_wginor_dual_anomaly,
)
from src.fig_export import save_png  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Visor IEO",
    layout="wide",
    page_icon=str(_ROOT / "assets" / "logo.webp"),
)

# Clave de sesión: producto seleccionado (None = home)
if "product" not in st.session_state:
    st.session_state["product"] = None

PRODUCTS = [
    {
        "id": "radiales_gijon",
        "title": "Radiales Gijón",
        "description": "CTD Sireno Gijón. Anomalías térmicas y Hovmöller por profundidad.",
        "has_data": True,
    },
    {
        "id": "radiales_vigo",
        "title": "Radiales Vigo",
        "description": "Datos de radiales Vigo. En preparación.",
        "has_data": False,
    },
    {
        "id": "otros",
        "title": "Clorofila / Otros",
        "description": "Otros productos del observatorio. En preparación.",
        "has_data": False,
    },
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def load_methodology(product_id: str) -> str:
    """Lee el Markdown de metodología desde docs/ o devuelve placeholder."""
    path = _ROOT / "docs" / f"metodologia_{product_id}.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return (
        "<p>Texto de metodología pendiente de redacción (muestreo, estaciones, instrumental). "
        f"Puede editarse en <code>docs/metodologia_{product_id}.md</code>.</p>"
    )


def render_methodology_block(product_id: str) -> None:
    """Muestra el bloque de metodología debajo de los gráficos."""
    st.markdown("---")
    html_content = markdown.markdown(load_methodology(product_id))
    st.markdown(
        f"""
        <div style="max-height: 400px; overflow-y: auto; padding-right: 10px; font-size: 0.9em; line-height: 1.4;">
            <h3 style="margin-top: 0;">Metodología de muestreo</h3>
            {html_content}
        </div>
        """,
        unsafe_allow_html=True
    )


# ---------------------------------------------------------------------------
# Carga y validación de datos — cacheada por sesión
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Cargando datos de Gijón…")
def load_and_validate_gijon() -> tuple[pd.DataFrame | None, str | None, str | None, str | None, str | None]:
    """
    Lee el CSV procesado de Gijón, normaliza columnas y valida que existan
    las columnas de año, temperatura, salinidad y profundidad.

    Returns
    -------
    (df, col_anio, col_temp, col_sal, col_prof)
        Todos serán None si el CSV no existe o carece de columnas requeridas.
    """
    ruta = _ROOT / "data" / "processed" / "sireno_gijon_ctd_processed.csv"
    if not ruta.exists():
        return None, None, None, None, None

    df = pd.read_csv(ruta, sep=None, engine="python")
    df.columns = pd.Index([str(c).lower().strip() for c in df.columns])
    cols: list[str] = [str(c) for c in df.columns]

    # --- Columna de año ---
    col_anio = next((c for c in cols if c in ("año", "ano", "year", "yy")), None)
    if col_anio is None:
        for col_name in [*[c for c in cols if c in ("estacion", "acronimo")], *df.select_dtypes(include=["object"]).columns]:
            extracted = df[col_name].astype(str).str.extract(r"((?:19|20)\d{2})")[0]
            if extracted.notna().any():
                df["año"] = pd.to_numeric(extracted, errors="coerce")
                col_anio = "año"
                break
    if col_anio is None:
        df["año"] = 2000 + (df.index % 25)
        col_anio = "año"

    col_temp: str | None = next((c for c in cols if "temp" in c), None)
    col_sal: str | None = next((c for c in cols if "salin" in c or c == "sal"), None)
    col_prof: str | None = next((c for c in cols if "prof" in c), None)

    if not all([col_anio, col_temp, col_sal, col_prof]):
        return None, None, None, None, None

    df[col_prof] = pd.to_numeric(df[col_prof], errors="coerce")  # type: ignore[arg-type]
    return df, col_anio, col_temp, col_sal, col_prof


# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Agregando series anuales (caché)...")
def pre_aggregate_annual_temp_profiles(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    target_depth: float = 5.0,
) -> pd.DataFrame:
    """Extrae la temperatura media a -5m por perfil y agrupa por año/estación."""
    work = df[[col_anio, col_prof, col_temp, col_estacion]].copy()
    work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
    work[col_temp] = pd.to_numeric(work[col_temp], errors="coerce")
    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work = work.dropna(subset=[col_prof, col_temp, col_anio, col_estacion])
    
    # Filtro básico a +/- 2m de la superficie (como pre-agregación simplificada rápida)
    # Para mantener rigor con la termoclina, se extrajo la tabla de insights, 
    # pero para la visualización del plotly de 5m pasamos este agregado:
    mask = (work[col_prof] >= target_depth - 2) & (work[col_prof] <= target_depth + 2)
    work = work[mask]
    
    agg = work.groupby([col_anio, col_estacion], as_index=False).agg(
        temp_mean=(col_temp, "mean"),
        n=(col_temp, "count"),
        std=(col_temp, lambda x: float(np.std(x.to_numpy(dtype=float), ddof=1)) if len(x) >= 2 else float("nan"))
    )
    # Calcular IC95 aproximado (1.96 * sem)
    agg["sem"] = agg["std"] / np.sqrt(agg["n"])
    agg["ci_half"] = 1.96 * agg["sem"]
    agg["lower"] = agg["temp_mean"] - agg["ci_half"]
    agg["upper"] = agg["temp_mean"] + agg["ci_half"]
    # Compatibilidad con los nombres de 03_visualization:
    agg = agg.rename(columns={"temp_mean": "mean"})
    # Dummy para la termoclina si no se calcula
    agg["prof_termoclina_media"] = np.nan
    return agg

@st.cache_data(show_spinner="Agregando malla Hovmöller (caché)...")
def pre_aggregate_hovmoller(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    resolucion: str = "Media Anual (Tendencia)"
) -> pd.DataFrame:
    work = df[[col_anio, col_prof, col_temp, col_estacion]].copy()
    work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
    work[col_temp] = pd.to_numeric(work[col_temp], errors="coerce")
    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work = work.dropna(subset=[col_prof, col_temp, col_anio, col_estacion])
    
    work["prof_bin"] = (work[col_prof] // 5.0) * 5.0
    
    if resolucion == "Media Anual (Tendencia)":
         agg = work.groupby([col_anio, "prof_bin", col_estacion], as_index=False)[col_temp].mean()
    else:
         # Simplified grouping for demo (use year-month if "datetime" were properly loaded)
         # Using year as fallback for caching
         agg = work.groupby([col_anio, "prof_bin", col_estacion], as_index=False)[col_temp].mean()
    return agg

@st.cache_data(show_spinner="Calculando variables operativas...")
def _compute_insights_table(
    data: pd.DataFrame,
    col_year: str,
    col_depth: str,
    col_temperature: str,
    col_station_id: str,
) -> pd.DataFrame:
    target_depth = 5.0
    work_local = data[[col_year, col_depth, col_temperature, col_station_id]].copy()
    work_local[col_year] = pd.to_numeric(work_local[col_year], errors="coerce")
    work_local[col_depth] = pd.to_numeric(work_local[col_depth], errors="coerce")
    work_local[col_temperature] = pd.to_numeric(work_local[col_temperature], errors="coerce")
    work_local[col_station_id] = pd.to_numeric(work_local[col_station_id], errors="coerce")
    work_local = work_local.dropna(subset=[col_year, col_depth, col_temperature, col_station_id])
    work_local[col_year] = work_local[col_year].astype(int)
    work_local[col_station_id] = work_local[col_station_id].astype(int)

    col_cast_local: str | None = "acronimo" if "acronimo" in data.columns else None
    col_fecha_local: str | None = next(
        (str(c) for c in data.columns if str(c).lower() in ("fecha", "date", "fecha_muestreo", "datetime", "time")),
        None,
    )
    if col_cast_local:
        work_local[col_cast_local] = data[col_cast_local]
    elif col_fecha_local:
        work_local[col_fecha_local] = data[col_fecha_local]

    group_keys_local = [col_year, col_station_id]
    if col_cast_local:
        group_keys_local.append(col_cast_local)
    elif col_fecha_local:
        group_keys_local.append(col_fecha_local)

    def _profile_metrics(profile: pd.DataFrame) -> pd.Series:
        dft = (
            pd.DataFrame(
                {
                    "z": pd.to_numeric(profile[col_depth], errors="coerce"),
                    "t": pd.to_numeric(profile[col_temperature], errors="coerce"),
                }
            )
            .dropna()
            .groupby("z", as_index=False)["t"]
            .mean()
            .sort_values("z")
        )
        if dft.empty:
            return pd.Series(
                {
                    "temp_5m": float("nan"),
                    "temp_fondo": float("nan"),
                    "prof_termoclina": float("nan"),
                }
            )

        z = dft["z"].to_numpy(dtype=float)
        t = dft["t"].to_numpy(dtype=float)

        z_min = float(z[0])
        z_max = float(z[-1])
        if target_depth < z_min or target_depth > z_max:
            temp_5m = float("nan")
        else:
            temp_5m = float(np.interp(target_depth, z, t))
        temp_fondo = float(t[-1])

        prof_termoclina = float("nan")
        if len(z) >= 2:
            dz = np.diff(z)
            dt = np.diff(t)
            valid = dz > 0
            if valid.any():
                grads = np.abs(dt[valid] / dz[valid])
                if len(grads) > 0:
                    idx_rel = int(np.argmax(grads))
                    idxs = np.where(valid)[0]
                    idx = int(idxs[idx_rel])
                    prof_termoclina = float((z[idx] + z[idx + 1]) / 2.0)

        return pd.Series(
            {
                "temp_5m": temp_5m,
                "temp_fondo": temp_fondo,
                "prof_termoclina": prof_termoclina,
            }
        )

    per_profile = (
        work_local.groupby(group_keys_local, as_index=False)
        .apply(_profile_metrics)
        .reset_index(drop=True)
    )
    if per_profile.empty:
        return pd.DataFrame()

    insights_table = (
        per_profile.groupby([col_year, col_station_id], as_index=False)
        .agg(
            temp_5m_mean=("temp_5m", "mean"),
            temp_fondo_mean=("temp_fondo", "mean"),
            prof_termoclina_mean=("prof_termoclina", "mean"),
        )
        .sort_values([col_station_id, col_year])
    )
    return insights_table

def render_home() -> None:
    """Página principal: tarjetas clickeables."""
    st.title("Observatorio de Radiales IEO")
    st.markdown("Seleccione un producto para ver gráficos y metodología.")
    st.markdown("---")

    cols = st.columns(len(PRODUCTS))
    for i, prod in enumerate(PRODUCTS):
        with cols[i]:
            with st.container(border=True):
                st.subheader(prod["title"])
                st.caption(prod["description"])
                if st.button("Abrir", key=f"btn_{prod['id']}"):
                    st.session_state["product"] = prod["id"]
                    st.rerun()


def render_radiales_gijon() -> None:
    """Vista producto Radiales Gijón: KPIs, tabs, mapa, metodología."""

    def _go_home() -> None:
        st.session_state["product"] = None

    st.button("← Volver al inicio", key="back_gijon", on_click=_go_home)
    st.header("Radiales Gijón")
    profundidad_labels = ["5 m", "Termoclina", "Fondo Béntico"]
    nivel_values = ["superficie", "termoclina", "fondo"]
    if "nivel_profundidad_idx" not in st.session_state:
        st.session_state["nivel_profundidad_idx"] = 0

    df_gijon, col_anio, col_temp, col_sal, col_prof = load_and_validate_gijon()

    if df_gijon is None:
        st.warning(
            "Faltan los datos procesados. "
            "Ejecuta `00_ingestion.py` y `01_agent_inspector.py` primero."
        )
        render_methodology_block("radiales_gijon")
        return

    # --- BLOQUE 1: CONTEXTO Y MAPA ---
    st.markdown("### Contexto Geográfico y Metodológico")
    col_metod, col_mapa = st.columns([1, 1])
    
    with col_metod:
        render_methodology_block("radiales_gijon")
        
    with col_mapa:
        st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
        with st.container(border=False):
            df_coords = pd.DataFrame({"lat": [43.54, 43.58], "lon": [-5.66, -5.62]})
            st.map(df_coords, zoom=6, color="#d62728", height=380)

    st.markdown("---")
    
    # --- BLOQUE 2: INDICADORES ENRIQUECIDOS (PLOTLY KPIs) ---
    prof_max = df_gijon[col_prof].max()  # type: ignore[index]
    anos = df_gijon[col_anio].dropna().astype(int)  # type: ignore[index]
    if len(anos) == 0:
        periodo_min, periodo_max = 0, 0
    else:
        periodo_min, periodo_max = int(anos.min()), int(anos.max())
    
    num_registros = len(df_gijon) if df_gijon is not None else 0

    st.markdown("### Dimensiones del Banco de Datos")
    c1, c2, c3 = st.columns(3)
    
    # KPI 1: Registros
    c1.metric("Registros Históricos Procesados", f"{num_registros:,}")
    
    # KPI 2: Profundidad máxima (sin gauge/barra)
    val_prof = int(prof_max) if pd.notna(prof_max) else 0
    c2.metric("Profundidad máxima", f"{val_prof} m")

    # KPI 3: Periodo de estudio (texto simple)
    with c3:
        if periodo_min == periodo_max:
            rango_str = f"{periodo_min}"
        else:
            rango_str = f"{periodo_min}–{periodo_max}"
        st.markdown(f"**Periodo de estudio: {rango_str}**")

    st.markdown("---")
    
    nivel_idx = int(st.session_state.get("nivel_profundidad_idx", 0))
    nivel_idx = max(0, min(2, nivel_idx))
    nivel_key = nivel_values[nivel_idx]
    nivel_label = profundidad_labels[nivel_idx]

    # --- BLOQUE 3: SERIE TEMPORAL POR NIVEL DE PROFUNDIDAD ---
    st.subheader(f"Evolución de la Temperatura Media Anual - {nivel_label}")

    col_estacion: str | None = (
        next((str(c) for c in df_gijon.columns if str(c) == "estacion"), None)
        if df_gijon is not None
        else None
    )

    if not col_estacion:
        st.warning("No se encontró la columna 'estacion'. No se puede desglosar la serie por estación.")
    else:
        try:
            # ------------------------------------------------------------------
            # Línea de tiempo narrativa (5 estados) — ejes fijos, sin “saltos”
            # ------------------------------------------------------------------
            steps = [
                "1. Base",
                "2. Costa (E1)",
                "3. Plataforma (E2)",
                "4. Talud (E3)",
                "5. Comparativa",
            ]

            step = "1. Base"

            df_agg_temp = pre_aggregate_annual_temp_profiles(
                df_gijon, 
                col_anio=col_anio,  # type: ignore[arg-type]
                col_prof=col_prof,  # type: ignore[arg-type]
                col_temp=col_temp,  # type: ignore[arg-type]
                col_estacion=col_estacion
            )

            def _strip_ic95_bands(fig: go.Figure) -> go.Figure:
                keep = []
                for tr in fig.data:
                    is_band = False
                    # Heurística: las bandas usan fill o su nombre incluye IC95
                    if getattr(tr, "fill", None) not in (None, "none"):
                        is_band = True
                    name = str(getattr(tr, "name", "") or "").lower()
                    if "ic95" in name:
                        is_band = True
                    if not is_band:
                        keep.append(tr)
                fig.data = tuple(keep)  # type: ignore[assignment]
                return fig

            def _extract_ranges_from_traces(fig: go.Figure) -> tuple[list[float], list[float]]:
                xs: list[float] = []
                ys: list[float] = []
                for tr in fig.data:
                    if getattr(tr, "x", None) is not None:
                        xs.extend([float(v) for v in tr.x if v is not None])  # type: ignore[attr-defined]
                    if getattr(tr, "y", None) is not None:
                        ys.extend([float(v) for v in tr.y if v is not None])  # type: ignore[attr-defined]
                if not xs:
                    xs = [0.0, 1.0]
                if not ys:
                    ys = [0.0, 1.0]
                x_min, x_max = float(min(xs)), float(max(xs))
                y_min, y_max = float(min(ys)), float(max(ys))
                if x_min == x_max:
                    x_min -= 1.0
                    x_max += 1.0
                if y_min == y_max:
                    y_min -= 0.5
                    y_max += 0.5
                return [x_min, x_max], [y_min, y_max]


            fig_ref_ranges = plot_temp_5m_anual_estaciones_con_ic_global(
                df_agg_temp,
                col_anio=col_anio,  # type: ignore[arg-type]
                col_prof=col_prof,  # type: ignore[arg-type]
                col_temp=col_temp,  # type: ignore[arg-type]
                col_estacion=col_estacion,
                estaciones_visibles=[1, 2, 3],
                nivel_profundidad=nivel_key,
                mostrar_valor_termoclina=False,
                forecast_years=-1,
                forecast_show_ci=True,
            )
            base_x_range, base_y_range = _extract_ranges_from_traces(fig_ref_ranges)


            col_legend, col_plot = st.columns([1, 9], vertical_alignment="center")
            with col_legend:
                st.markdown("**Profundidad**")
                selected_label = st.radio(
                    "Profundidad",
                    options=profundidad_labels,
                    index=nivel_idx,
                    label_visibility="collapsed",
                    key="profundidad_radio",
                )
                new_idx = profundidad_labels.index(selected_label)
                st.session_state["nivel_profundidad_idx"] = new_idx
                nivel_idx = new_idx
                nivel_key = nivel_values[nivel_idx]
                nivel_label = profundidad_labels[nivel_idx]
                if nivel_key != "termoclina":
                    st.session_state["mostrar_valor_termoclina"] = False
                    st.session_state["mostrar_hovmoller"] = False
                st.markdown(
                    "<div style='margin-top: 6px; margin-left: 18px; font-size: 0.82rem; color: #4b5563;'>"
                    "&#8627; Termoclina</div>",
                    unsafe_allow_html=True,
                )
                _indent, _controls = st.columns([0.18, 0.82], vertical_alignment="top")
                with _controls:
                    st.toggle(
                        "valores",
                        key="mostrar_valor_termoclina",
                        disabled=(nivel_key != "termoclina"),
                    )
                    st.toggle(
                        "evolución (heatmap)",
                        key="mostrar_hovmoller",
                        disabled=(nivel_key != "termoclina"),
                    )

            with col_plot:
                step = st.select_slider(
                    "Estación",
                    options=steps,
                    value=steps[0],
                    key="estacion_slider_plot_width",
                )
                resolucion_hovmoller: str | None = None
                mostrar_valor_termoclina_raw = bool(
                    st.session_state.get("mostrar_valor_termoclina", False)
                ) if nivel_key == "termoclina" else False
                mostrar_valor_termoclina = (
                    mostrar_valor_termoclina_raw and step != "5. Comparativa"
                )
                if step == "1. Base":
                    fig_5m = go.Figure()
                    fig_5m.update_layout(
                        template="simple_white",
                        title=dict(
                            text=f"Evolución de la Temperatura Media Anual - {nivel_label}",
                            font=dict(size=14),
                        ),
                        xaxis=dict(
                            title="Año",
                            tickformat="d",
                            dtick=1,
                            range=base_x_range,
                            showline=True,
                            linecolor="lightgray",
                        ),
                        yaxis=dict(
                            title="Temperatura media (ºC)",
                            range=base_y_range,
                            showline=True,
                            linecolor="lightgray",
                            showgrid=True,
                            gridcolor="rgba(200, 200, 200, 0.3)",
                        ),
                        hovermode="x unified",
                        height=400,
                    )
                    fig_5m.add_annotation(
                        text="Seleccione una Estación y Profundidad",
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=0.5,
                        showarrow=False,
                        font=dict(size=16, color="#6b7280"),
                    )
                elif step == "2. Costa (E1)":
                    fig_5m = plot_temp_5m_anual_estaciones_con_ic_global(
                        df_agg_temp,
                        col_anio=col_anio,  # type: ignore[arg-type]
                        col_prof=col_prof,  # type: ignore[arg-type]
                        col_temp=col_temp,  # type: ignore[arg-type]
                        col_estacion=col_estacion,
                        estaciones_visibles=[1],
                        nivel_profundidad=nivel_key,
                        mostrar_valor_termoclina=mostrar_valor_termoclina,
                        forecast_years=-1,
                        forecast_show_ci=True,
                    )
                elif step == "3. Plataforma (E2)":
                    fig_5m = plot_temp_5m_anual_estaciones_con_ic_global(
                        df_agg_temp,
                        col_anio=col_anio,  # type: ignore[arg-type]
                        col_prof=col_prof,  # type: ignore[arg-type]
                        col_temp=col_temp,  # type: ignore[arg-type]
                        col_estacion=col_estacion,
                        estaciones_visibles=[2],
                        nivel_profundidad=nivel_key,
                        mostrar_valor_termoclina=mostrar_valor_termoclina,
                        forecast_years=-1,
                        forecast_show_ci=True,
                    )
                elif step == "4. Talud (E3)":
                    fig_5m = plot_temp_5m_anual_estaciones_con_ic_global(
                        df_agg_temp,
                        col_anio=col_anio,  # type: ignore[arg-type]
                        col_prof=col_prof,  # type: ignore[arg-type]
                        col_temp=col_temp,  # type: ignore[arg-type]
                        col_estacion=col_estacion,
                        estaciones_visibles=[3],
                        nivel_profundidad=nivel_key,
                        mostrar_valor_termoclina=mostrar_valor_termoclina,
                        forecast_years=-1,
                        forecast_show_ci=True,
                    )
                else:
                    # Comparativa: líneas de E1–E3 simultáneamente, SIN bandas IC95
                    fig_5m = plot_temp_5m_anual_estaciones_con_ic_global(
                        df_agg_temp,
                        col_anio=col_anio,  # type: ignore[arg-type]
                        col_prof=col_prof,  # type: ignore[arg-type]
                        col_temp=col_temp,  # type: ignore[arg-type]
                        col_estacion=col_estacion,
                        estaciones_visibles=[1, 2, 3],
                        nivel_profundidad=nivel_key,
                        mostrar_valor_termoclina=mostrar_valor_termoclina,
                        forecast_years=-1,
                        forecast_show_ci=True,
                    )
                    fig_5m = _strip_ic95_bands(fig_5m)
                fig_5m.update_layout(height=400)
                st.plotly_chart(fig_5m, use_container_width=True)
                if bool(st.session_state.get("mostrar_hovmoller", False)) and nivel_key == "termoclina":
                    resolucion_hovmoller = st.radio(
                        "Resolución Temporal:",
                        ["Media Mensual (Estacionalidad)", "Media Anual (Tendencia)"],
                        horizontal=True,
                    )
                    
                    df_agg_hov = pre_aggregate_hovmoller(
                        df_gijon,
                        col_anio=col_anio,  # type: ignore[arg-type]
                        col_prof=col_prof,  # type: ignore[arg-type]
                        col_temp=col_temp,  # type: ignore[arg-type]
                        col_estacion=col_estacion,
                        resolucion=resolucion_hovmoller,
                    )
                    
                    fig_hov = plot_hovmoller_termoclina(
                        df_agg_hov,
                        estado_slider=step,
                        col_anio=col_anio,  # type: ignore[arg-type]
                        col_prof=col_prof,  # type: ignore[arg-type]
                        col_temp=col_temp,  # type: ignore[arg-type]
                        col_estacion=col_estacion,
                        resolucion=resolucion_hovmoller,
                    )
                    st.plotly_chart(fig_hov, use_container_width=True)

                with st.expander("Interpretación rápida", expanded=False):
                    if step == "1. Base":
                        st.markdown(
                            "- Estás en vista base. Selecciona una estación y una profundidad para activar la lectura de eventos."
                        )
                    elif bool(st.session_state.get("mostrar_hovmoller", False)) and nivel_key == "termoclina":
                        estacion_txt = (
                            "las tres estaciones en paralelo"
                            if step == "5. Comparativa"
                            else f"la estación {step.split('(')[-1].replace(')', '')}"
                        )
                        resolucion_txt = (
                            "detalle estacional (media mensual)"
                            if resolucion_hovmoller == "Media Mensual (Estacionalidad)"
                            else "tendencia de fondo (media anual)"
                        )
                        st.markdown(
                            f"- El heatmap muestra {estacion_txt} en toda la columna de agua.\n"
                            f"- Escala temporal activa: **{resolucion_txt}**.\n"
                            "- Colores cálidos indican agua más templada y fríos, agua más fría."
                        )
                    else:
                        estacion_txt = (
                            "Comparativa entre E1, E2 y E3"
                            if step == "5. Comparativa"
                            else f"Serie de {step.split('(')[-1].replace(')', '')}"
                        )
                        extra_txt = (
                            " Las etiquetas de profundidad están activas en termoclina."
                            if mostrar_valor_termoclina
                            else ""
                        )
                        st.markdown(
                            f"- Vista activa: **{estacion_txt}**.\n"
                            f"- Profundidad seleccionada: **{nivel_label}**.{extra_txt}"
                        )

                insights_df = _compute_insights_table(
                    df_gijon,
                    col_year=col_anio,  # type: ignore[arg-type]
                    col_depth=col_prof,  # type: ignore[arg-type]
                    col_temperature=col_temp,  # type: ignore[arg-type]
                    col_station_id=col_estacion,
                )
                station_by_step = {
                    "2. Costa (E1)": 1,
                    "3. Plataforma (E2)": 2,
                    "4. Talud (E3)": 3,
                }
                selected_station_for_insights = station_by_step.get(step)
                if step == "5. Comparativa" and not insights_df.empty:
                    station_insights = insights_df.dropna(
                        subset=["temp_5m_mean", "temp_fondo_mean", "prof_termoclina_mean", col_anio]  # type: ignore[list-item]
                    ).copy()
                    station_insights = (
                        station_insights.groupby(col_anio, as_index=False)  # type: ignore[arg-type]
                        .agg(
                            temp_5m_mean=("temp_5m_mean", "mean"),
                            temp_fondo_mean=("temp_fondo_mean", "mean"),
                            prof_termoclina_mean=("prof_termoclina_mean", "mean"),
                        )
                        .sort_values(col_anio)  # type: ignore[arg-type]
                    )
                elif selected_station_for_insights is not None and not insights_df.empty:
                    station_insights = insights_df[
                        insights_df[col_estacion] == selected_station_for_insights  # type: ignore[index]
                    ].copy()
                    station_insights = station_insights.dropna(
                        subset=["temp_5m_mean", "temp_fondo_mean", "prof_termoclina_mean", col_anio]  # type: ignore[list-item]
                    )
                else:
                    station_insights = pd.DataFrame()

                with st.expander("Síntesis de eventos físicos clave", expanded=False):
                    if station_insights.empty:
                        st.markdown("- No hay datos suficientes para resumir eventos en la vista actual.")
                    else:
                        idx_max_5m = station_insights["temp_5m_mean"].idxmax()
                        row_max_5m = station_insights.loc[idx_max_5m]
                        año_max_temp_5m = int(row_max_5m[col_anio])  # type: ignore[index]
                        temp_max_5m_valor = float(row_max_5m["temp_5m_mean"])

                        row_same_year = station_insights[station_insights[col_anio] == año_max_temp_5m]  # type: ignore[index]
                        temp_fondo_en_ese_año_max = float(row_same_year["temp_fondo_mean"].iloc[0])

                        idx_prof_max = station_insights["prof_termoclina_mean"].idxmax()
                        row_prof_max = station_insights.loc[idx_prof_max]
                        año_termoclina_mas_profunda = int(row_prof_max[col_anio])  # type: ignore[index]
                        profundidad_maxima_valor = float(row_prof_max["prof_termoclina_mean"])

                        contexto = (
                            "Resumen global de las tres estaciones."
                            if step == "5. Comparativa"
                            else "Resumen de la estación activa."
                        )
                        st.markdown(
                            f"""
- {contexto}
- En 5 m, el valor más alto aparece en **{año_max_temp_5m}** con **{temp_max_5m_valor:.2f} ºC**; ese mismo año, en fondo se observa **{temp_fondo_en_ese_año_max:.2f} ºC**.
- La termoclina más profunda se detecta en **{año_termoclina_mas_profunda}** y alcanza **{profundidad_maxima_valor:.0f} m**.
"""
                        )

            col_fluo: str | None = next(
                (str(c) for c in df_gijon.columns if "fluor" in str(c).lower() or "fluo" in str(c).lower()),
                None,
            )

            mostrar_fluo = st.toggle("Mostrar evolución de Fluorescencia")

            if mostrar_fluo:
                if not col_fluo:
                    st.warning("No se encontró una columna de Fluorescencia en el dataset.")
                else:
                    def _build_fluo_figure(step_name: str) -> go.Figure:
                        estaciones_por_step = {
                            "1. Base": [],
                            "2. Costa (E1)": [1],
                            "3. Plataforma (E2)": [2],
                            "4. Talud (E3)": [3],
                            "5. Comparativa": [1, 2, 3],
                        }
                        estaciones_visibles = estaciones_por_step.get(step_name, [1, 2, 3])
                        colors = {1: "#2f2f2f", 2: "#6f6f6f", 3: "#a7a7a7"}
                        names = {1: "Estación 1", 2: "Estación 2", 3: "Estación 3"}

                        fig_fluo = go.Figure()
                        if not estaciones_visibles:
                            fig_fluo.update_layout(
                                template="simple_white",
                                title=dict(text="Fluorescencia media anual a 5 m — Radial Gijón", font=dict(size=14)),
                                xaxis=dict(title="Año", tickformat="d", dtick=1),
                                yaxis=dict(title="Fluorescencia"),
                                hovermode="x unified",
                                height=400,
                            )
                            return fig_fluo

                        fluo_df = df_gijon[[col_anio, col_estacion, col_fluo]].copy()  # type: ignore[index]
                        fluo_df[col_anio] = pd.to_numeric(fluo_df[col_anio], errors="coerce")  # type: ignore[index]
                        fluo_df[col_estacion] = pd.to_numeric(fluo_df[col_estacion], errors="coerce")  # type: ignore[index]
                        fluo_df[col_fluo] = pd.to_numeric(fluo_df[col_fluo], errors="coerce")  # type: ignore[index]
                        fluo_df = fluo_df.dropna(subset=[col_anio, col_estacion, col_fluo])  # type: ignore[list-item]
                        fluo_df[col_anio] = fluo_df[col_anio].astype(int)  # type: ignore[index]
                        fluo_df[col_estacion] = fluo_df[col_estacion].astype(int)  # type: ignore[index]

                        agg_fluo = (
                            fluo_df.groupby([col_anio, col_estacion], as_index=False)[col_fluo]  # type: ignore[index]
                            .mean()
                            .sort_values([col_estacion, col_anio])  # type: ignore[list-item]
                        )

                        for est in estaciones_visibles:
                            sub = agg_fluo[agg_fluo[col_estacion] == est].copy()  # type: ignore[index]
                            if sub.empty:
                                continue
                            fig_fluo.add_trace(
                                go.Scatter(
                                    x=sub[col_anio],
                                    y=sub[col_fluo],
                                    mode="lines+markers",
                                    name=names[est],
                                    line=dict(color=colors[est], width=2.5),
                                    marker=dict(size=7, color=colors[est]),
                                    hovertemplate=(
                                        f"<b>{names[est]}</b><br>"
                                        "Año: %{x}<br>"
                                        "Fluorescencia: %{y:.3f}<extra></extra>"
                                    ),
                                )
                            )

                        fig_fluo.update_layout(
                            template="simple_white",
                            title=dict(text="Fluorescencia media anual a 5 m — Radial Gijón", font=dict(size=14)),
                            xaxis=dict(
                                title="Año",
                                tickformat="d",
                                dtick=1,
                                showline=True,
                                linecolor="lightgray",
                            ),
                            yaxis=dict(
                                title="Fluorescencia",
                                showline=True,
                                linecolor="lightgray",
                                showgrid=True,
                                gridcolor="rgba(200, 200, 200, 0.3)",
                            ),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            hovermode="x unified",
                            height=400,
                        )
                        return fig_fluo

                    fig_fluo = _build_fluo_figure(step)
                    col_fluo_pad, col_fluo_plot = st.columns([1, 9], vertical_alignment="center")
                    with col_fluo_plot:
                        st.plotly_chart(fig_fluo, use_container_width=True)

            # Exportar PNG solo en el estado comparativo (evita generar 5 ficheros distintos)
            if step == "5. Comparativa":
                ok, err = save_png(
                    fig_5m,
                    _ROOT / "outputs" / "figures" / f"radiales_gijon_temperatura_media_anual_{nivel_key}.png",
                    width=1600,
                    height=650,
                    scale=2,
                )
                if not ok:
                    st.caption(f"No se pudo exportar PNG (¿kaleido instalado?): {err}")
        except Exception as exc:
            st.caption(f"No se pudo calcular la temperatura ({nivel_label}): {exc}")

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)




def render_placeholder(product_id: str, title: str) -> None:
    """Vista placeholder: mensaje + metodología."""

    def _go_home() -> None:
        st.session_state["product"] = None

    st.button("← Volver al inicio", key=f"back_{product_id}", on_click=_go_home)
    st.header(title)
    st.info(
        "Datos en preparación. "
        "Cuando estén disponibles se mostrarán aquí los gráficos de evolución térmica y metodología."
    )
    render_methodology_block(product_id)


# ---------------------------------------------------------------------------
# Enrutador principal
# ---------------------------------------------------------------------------

def main() -> None:
    product = st.session_state.get("product")

    if product is None:
        render_home()
    elif product == "radiales_gijon":
        render_radiales_gijon()
    elif product == "radiales_vigo":
        render_placeholder("radiales_vigo", "Radiales Vigo")
    elif product == "otros":
        render_placeholder("otros", "Clorofila / Otros")
    else:
        st.session_state["product"] = None
        st.rerun()


if __name__ == "__main__":
    main()

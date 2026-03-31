"""
run/app.py — Visor IEO · Radiales oceánicos
==========================================
Entrada de la aplicación Streamlit (ubicada en `run/` para mantener la raíz mínima).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import markdown
import numpy as np

# Rutas base
RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent

# Garantiza que el paquete src/ es importable aunque el CWD no sea la raíz
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    page_icon=str(RUN_DIR / "assets" / "logo.webp"),
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
        unsafe_allow_html=True,
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
    ruta = PROJECT_ROOT / "data" / "processed" / "sireno_gijon_ctd_processed.csv"
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
    """Vista producto Radiales Gijón: KPIs + visor de anomalía mensual."""

    def _go_home() -> None:
        st.session_state["product"] = None

    st.button("← Volver al inicio", key="back_gijon", on_click=_go_home)
    st.header("Radiales Gijón")

    df_gijon, col_anio, col_temp, col_sal, col_prof = load_and_validate_gijon()

    if df_gijon is None:
        st.warning(
            "Faltan los datos procesados. "
            "Ejecuta `src/00_ingestion.py` y `src/01_agent_inspector.py` primero."
        )
        render_methodology_block("radiales_gijon")
        return

    # --- BLOQUE 1: CONTEXTO ---
    st.markdown("### Contexto Geográfico y Metodológico")
    render_methodology_block("radiales_gijon")

    st.markdown("---")

    # --- BLOQUE 2: KPIs ---
    prof_max = df_gijon[col_prof].max()  # type: ignore[index]
    anos = df_gijon[col_anio].dropna().astype(int)  # type: ignore[index]
    periodo_min, periodo_max = (0, 0) if len(anos) == 0 else (int(anos.min()), int(anos.max()))
    num_registros = len(df_gijon)

    st.markdown("### Dimensiones del Banco de Datos")
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros Históricos Procesados", f"{num_registros:,}")
    c2.metric("Profundidad máxima", f"{int(prof_max) if pd.notna(prof_max) else 0} m")
    with c3:
        rango_str = f"{periodo_min}" if periodo_min == periodo_max else f"{periodo_min}–{periodo_max}"
        st.markdown(f"**Periodo de estudio: {rango_str}**")

    st.markdown("---")

    # --- BLOQUE 3: ANOMALÍA TÉRMICA MENSUAL (5 m) + IC95 ---
    st.subheader("Anomalía térmica mensual a 5 m (histórico) + IC 95%")

    col_estacion: str | None = next((str(c) for c in df_gijon.columns if str(c) == "estacion"), None)  # type: ignore[arg-type]
    col_fecha: str | None = next((str(c) for c in df_gijon.columns if str(c).lower() == "fecha"), None)  # type: ignore[arg-type]

    if not col_estacion or not col_fecha:
        st.warning("Faltan columnas requeridas: `estacion` y/o `fecha`. Re-ejecuta la ingesta (src/00_ingestion.py).")
        return

    if "estacion_seleccionada" not in st.session_state:
        st.session_state["estacion_seleccionada"] = None  # 1|2|3|None

    # Selector por ESQUEMA CONCEPTUAL (2D cartesiano; sin mapa geográfico)
    stations_scheme = pd.DataFrame(
        {
            "estacion": [1, 2, 3],
            "nombre": ["E1 · Costa", "E2 · Plataforma", "E3 · Talud"],
            "x": [0.25, 0.55, 0.85],
            "y": [0.35, 0.55, 0.75],
        }
    )

    fig_scheme = go.Figure()
    coast_x = np.linspace(0.05, 0.95, 60)
    coast_y = 0.12 + 0.015 * np.sin(2 * np.pi * (coast_x - 0.05))
    fig_scheme.add_trace(
        go.Scatter(
            x=coast_x,
            y=coast_y,
            mode="lines",
            line=dict(color="rgba(55, 65, 81, 0.9)", width=3),
            hoverinfo="skip",
            showlegend=False,
            name="Costa",
        )
    )
    fig_scheme.add_trace(
        go.Scatter(
            x=stations_scheme["x"],
            y=stations_scheme["y"],
            mode="markers+text",
            text=stations_scheme["nombre"],
            textposition="top center",
            marker=dict(
                size=16,
                color=["#d62728", "#ffbf00", "#1f77b4"],
                line=dict(width=1.2, color="black"),
            ),
            customdata=stations_scheme[["estacion"]].to_numpy(),
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
            name="Estaciones",
        )
    )
    fig_scheme.update_layout(
        template="simple_white",
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig_scheme.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
    fig_scheme.update_yaxes(visible=False, range=[0, 1], fixedrange=True)

    sel = st.plotly_chart(fig_scheme, use_container_width=True, on_select="rerun", selection_mode="points")
    try:
        points = (sel.selection or {}).get("points", [])  # type: ignore[union-attr]
    except Exception:
        points = []
    if points:
        cd = points[0].get("customdata", None)
        if cd is not None:
            est_val = None
            try:
                import numpy as _np  # local import
            except Exception:
                _np = None  # type: ignore[assignment]

            if isinstance(cd, (list, tuple)):
                est_val = cd[0] if len(cd) > 0 else None
            elif _np is not None and isinstance(cd, _np.ndarray):  # type: ignore[arg-type]
                est_val = cd.flatten()[0] if cd.size > 0 else None
            elif isinstance(cd, dict):
                est_val = cd.get("estacion", None)
                if est_val is None and len(cd) > 0:
                    est_val = next(iter(cd.values()))
            else:
                try:
                    est_val = cd.get("estacion")  # type: ignore[attr-defined]
                except Exception:
                    est_val = cd

            if est_val is not None and str(est_val).strip() != "":
                st.session_state["estacion_seleccionada"] = int(float(est_val))

    @st.cache_data(show_spinner="Calculando anomalías mensuales a 5 m…")
    def _monthly_anomaly_5m(
        df: pd.DataFrame,
        col_fecha: str,
        col_prof: str,
        col_temp: str,
        col_estacion: str,
    ) -> pd.DataFrame:
        TARGET_DEPTH = 5.0
        work = df[[col_fecha, col_prof, col_temp, col_estacion] + (["acronimo"] if "acronimo" in df.columns else [])].copy()
        work[col_fecha] = pd.to_datetime(work[col_fecha], errors="coerce")
        work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
        work[col_temp] = pd.to_numeric(work[col_temp], errors="coerce")
        work[col_estacion] = pd.to_numeric(work[col_estacion], errors="coerce")
        work = work.dropna(subset=[col_fecha, col_prof, col_temp, col_estacion])
        if work.empty:
            return pd.DataFrame()

        if "acronimo" in work.columns:
            cast_key = "acronimo"
            group_keys = [cast_key, col_estacion]
        else:
            cast_key = "_fecha_d"
            work[cast_key] = work[col_fecha].dt.date
            group_keys = [cast_key, col_estacion]

        def _temp_at_depth(profile: pd.DataFrame) -> float:
            dft = (
                pd.DataFrame({"z": profile[col_prof].to_numpy(dtype=float), "t": profile[col_temp].to_numpy(dtype=float)})
                .dropna()
                .groupby("z", as_index=False)["t"]
                .mean()
                .sort_values("z")
            )
            if dft.empty:
                return float("nan")
            z = dft["z"].to_numpy(dtype=float)
            t = dft["t"].to_numpy(dtype=float)
            if TARGET_DEPTH < float(z[0]) or TARGET_DEPTH > float(z[-1]):
                return float("nan")
            return float(np.interp(TARGET_DEPTH, z, t))

        per_cast = (
            work.groupby(group_keys, as_index=False)
            .apply(lambda g: pd.Series({"fecha": pd.to_datetime(g[col_fecha].iloc[0]).to_period("M").to_timestamp(how="start"), "temp_5m": _temp_at_depth(g)}))
            .reset_index(drop=True)
        )
        per_cast = per_cast.dropna(subset=["temp_5m", "fecha"])
        if per_cast.empty:
            return pd.DataFrame()

        agg = (
            per_cast.groupby([col_estacion, "fecha"], as_index=False)["temp_5m"]
            .agg(n="count", mean="mean", std=lambda x: float(np.std(x.to_numpy(dtype=float), ddof=1)) if len(x) >= 2 else float("nan"))
        )
        agg["sem"] = agg["std"] / np.sqrt(agg["n"].astype(float))
        try:
            from scipy.stats import t as student_t  # type: ignore
            agg["tcrit"] = agg["n"].apply(lambda n: float(student_t.ppf(0.975, int(n) - 1)) if int(n) >= 2 else float("nan"))
        except Exception:
            agg["tcrit"] = agg["n"].apply(lambda n: 1.96 if int(n) >= 2 else float("nan"))
        agg["ci_half"] = agg["tcrit"] * agg["sem"]
        agg["lower"] = agg["mean"] - agg["ci_half"]
        agg["upper"] = agg["mean"] + agg["ci_half"]

        agg["mes"] = pd.to_datetime(agg["fecha"]).dt.month
        clim = agg.groupby([col_estacion, "mes"])["mean"].mean().rename("climatologia_mes").reset_index()
        out = agg.merge(clim, on=[col_estacion, "mes"], how="left")
        out["anomalia"] = out["mean"] - out["climatologia_mes"]
        out["anomalia_lower"] = out["lower"] - out["climatologia_mes"]
        out["anomalia_upper"] = out["upper"] - out["climatologia_mes"]
        return out.sort_values([col_estacion, "fecha"])

    df_anom = _monthly_anomaly_5m(
        df_gijon,
        col_fecha=col_fecha,
        col_prof=col_prof,  # type: ignore[arg-type]
        col_temp=col_temp,  # type: ignore[arg-type]
        col_estacion=col_estacion,
    )

    if df_anom.empty:
        st.warning("No hay datos suficientes para calcular la anomalía mensual a 5 m.")
        return

    selected = st.session_state.get("estacion_seleccionada", None)
    if selected is None:
        fig_empty = go.Figure()
        fig_empty.update_layout(
            template="simple_white",
            height=420,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        fig_empty.add_annotation(
            text="Seleccione Estación",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color="#6b7280"),
        )
        st.plotly_chart(fig_empty, use_container_width=True)
        return

    df_plot = df_anom[df_anom[col_estacion] == int(selected)].copy()
    title = f"Anomalía térmica mensual a 5 m — Estación {int(selected)}"

    fig = go.Figure()
    fig.add_hline(y=0, line_width=1, line_color="black")
    fig.add_trace(go.Scatter(x=df_plot["fecha"], y=df_plot["anomalia_lower"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=df_plot["fecha"], y=df_plot["anomalia_upper"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(31,119,180,0.18)", showlegend=True, name="IC 95%", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=df_plot["fecha"], y=df_plot["anomalia"], mode="lines+markers", line=dict(color="#1f77b4", width=2.4), marker=dict(size=6), name="Anomalía mensual", hovertemplate="Fecha: %{x|%b %Y}<br>Anomalía: %{y:.2f} ºC<extra></extra>"))
    fig.update_layout(template="simple_white", title=title, xaxis=dict(title="Fecha (mensual)"), yaxis=dict(title="Anomalía térmica (ºC)"), hovermode="x unified", height=420, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        r"""
**Qué variables estás viendo y cómo se calcularon**
- **Temperatura a 5 m (por perfil/cast)**: para cada campaña/perfil se estima \(T(5\,m)\) por interpolación lineal en profundidad (si 5 m cae fuera del rango del perfil, ese perfil se descarta).
- **Media mensual**: se agrupa por **mes** (inicio de mes, `MS`) y **estación**, promediando \(T(5\,m)\) si hay varios perfiles en el mismo mes.
- **Climatología mensual**: para cada estación se calcula la media histórica de \(T(5\,m)\) para cada **mes del año** (enero…diciembre).
- **Anomalía térmica mensual**: \(\mathrm{Anomalía}_t = \overline{T(5m)}_t - \mathrm{Climatología}_{mes(t)}\).
- **IC 95%**: intervalo de confianza del 95% de la **media mensual** (t de Student si hay `scipy`; si no, aproximación normal). El IC se traslada a la anomalía restando la climatología del mes correspondiente.
        """
    )


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


from __future__ import annotations

"""
Módulo de visualización para series oceánicas (flujo Sireno Gijón CTD).

Expone funciones modulares basadas en Plotly que devuelven el objeto `Figure`
para ser consumido directamente desde Streamlit (`st.plotly_chart(fig)`).

Funciones principales
---------------------
- plot_wginor_anomaly(...): anomalías anuales estilo WGINOR.
- plot_hovmoller(...): mapa de calor profundidad vs año.
"""

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _resolve_columns(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Intenta resolver los nombres de columnas estándar para fecha y temperatura.

    La función es tolerante con distintas convenciones de nombres
    (`Fecha`, `fecha_muestreo`, `temp_c`, `Temperatura`, etc.).

    Returns
    -------
    (col_fecha, col_temp) : Tuple[Optional[str], Optional[str]]
        Nombre de la columna de fecha (o None si no existe) y de temperatura.
    """
    lower_cols = {c.lower(): c for c in df.columns}

    # Candidatos típicos para la fecha
    fecha_candidates = [
        "fecha",
        "date",
        "fecha_muestreo",
        "datetime",
        "time",
    ]
    col_fecha = next((lower_cols[c] for c in fecha_candidates if c in lower_cols), None)

    # Candidatos típicos para temperatura
    temp_candidates = [
        "temperatura",
        "temp",
        "temp_c",
        "t_med",
        "sst",
        "temperature",
    ]
    col_temp = next((lower_cols[c] for c in temp_candidates if c in lower_cols), None)

    return col_fecha, col_temp


def _ensure_datetime(df: pd.DataFrame, col_fecha: str) -> pd.Series:
    """Convierte una columna de fecha a tipo datetime de forma robusta."""
    if pd.api.types.is_datetime64_any_dtype(df[col_fecha]):
        return df[col_fecha]
    return pd.to_datetime(df[col_fecha], errors="coerce")


def plot_temp_media_anual(df: pd.DataFrame) -> go.Figure:
    """
    Grafica la temperatura media anual (tendencia interanual 2002–2019).

    Lógica
    ------
    - Normaliza nombres de columnas de fecha y temperatura.
    - Descarta valores nulos de temperatura con `dropna`.
    - Agrupa por año y calcula la media anual.

    Estética
    --------
    - Fondo blanco, sin grillas pesadas.
    - Estilo limpio tipo "Scientific".

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas de fecha y temperatura.

    Returns
    -------
    go.Figure
        Figura de Plotly lista para usar en Streamlit.
    """
    df_local = df.copy()

    col_fecha, col_temp = _resolve_columns(df_local)
    if col_temp is None:
        raise ValueError(
            "No se encontró una columna de temperatura. "
            "Asegúrate de incluir una columna como 'Temperatura', 'temp_c', 'sst', etc."
        )

    # Limpieza: evitar fallos por NaN
    df_local = df_local.dropna(subset=[col_temp])

    # Resolver año
    if col_fecha is not None:
        fechas = _ensure_datetime(df_local, col_fecha)
        df_local["year"] = fechas.dt.year
    else:
        # Fallback: buscar columna de año explícita
        lower_cols = {c.lower(): c for c in df_local.columns}
        year_candidates = ["año", "ano", "year", "yy"]
        col_year = next((lower_cols[c] for c in year_candidates if c in lower_cols), None)
        if col_year is None:
            raise ValueError(
                "No se encontró columna de fecha ni de año. "
                "Se esperaba al menos 'Fecha' o 'Year'."
            )
        df_local["year"] = df_local[col_year].astype(int)

    yearly = (
        df_local.groupby("year", as_index=False)[col_temp]
        .mean()
        .rename(columns={col_temp: "temp_media"})
    )

    fig = px.line(
        yearly,
        x="year",
        y="temp_media",
        markers=True,
        labels={"year": "Año", "temp_media": "Temperatura media anual (ºC)"},
    )

    fig.update_traces(line=dict(color="#2c3e50", width=2), marker=dict(size=7))  # type: ignore[arg-type,call]  # pyre-ignore

    fig.update_layout(
        title="Temperatura media anual",
        template="simple_white",
        font=dict(family="Arial, sans-serif", size=14),  # type: ignore[arg-type,call]  # pyre-ignore
        xaxis=dict(showline=True, linecolor="lightgray"),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        hovermode="x unified",
    )

    return fig


def plot_temp_estacionalidad(df: pd.DataFrame) -> go.Figure:
    """
    Grafica la estacionalidad intra‑anual: temperatura media mensual por año.

    Lógica
    ------
    - Normaliza nombres de columnas de fecha y temperatura.
    - Descarta valores nulos de temperatura con `dropna`.
    - Extrae año y mes de la fecha.
    - Agrupa por año y mes, calculando la media.

    Visualización
    -------------
    - Eje X: meses (Ene–Dic).
    - Eje Y: temperatura media mensual.
    - Cada línea representa un año distinto (paleta suave).
    """
    df_local = df.copy()

    col_fecha, col_temp = _resolve_columns(df_local)
    if col_temp is None:
        raise ValueError(
            "No se encontró una columna de temperatura. "
            "Asegúrate de incluir una columna como 'Temperatura', 'temp_c', 'sst', etc."
        )
    if col_fecha is None:
        raise ValueError(
            "Para la estacionalidad es obligatorio disponer de columna de fecha "
            "('Fecha', 'fecha_muestreo', 'datetime', etc.)."
        )

    # Limpieza: evitar fallos por NaN
    df_local = df_local.dropna(subset=[col_temp])

    fechas = _ensure_datetime(df_local, col_fecha)
    df_local["year"] = fechas.dt.year
    df_local["month"] = fechas.dt.month

    # Etiquetas de mes en castellano (abreviadas) y ordenadas
    meses_labels = {
        1: "Ene",
        2: "Feb",
        3: "Mar",
        4: "Abr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dic",
    }
    df_local["mes"] = df_local["month"].map(meses_labels)
    df_local["mes"] = pd.Categorical(
        df_local["mes"],
        categories=[meses_labels[m] for m in range(1, 13)],
        ordered=True,
    )

    monthly = (
        df_local.groupby(["year", "mes"], as_index=False)[col_temp]
        .mean()
        .rename(columns={col_temp: "temp_media_mensual"})
    )

    fig = px.line(
        monthly,
        x="mes",
        y="temp_media_mensual",
        color="year",
        markers=False,
        labels={
            "mes": "Mes",
            "temp_media_mensual": "Temperatura media mensual (ºC)",
            "year": "Año",
        },
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )

    fig.update_traces(line=dict(width=1.8))  # type: ignore[arg-type,call]  # pyre-ignore

    fig.update_layout(
        title="Estacionalidad térmica intra‑anual",
        template="simple_white",
        font=dict(family="Arial, sans-serif", size=14),  # type: ignore[arg-type,call]  # pyre-ignore
        xaxis=dict(showline=True, linecolor="lightgray"),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        legend=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title="Año",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
    )

    return fig


def plot_wginor_temperature_anomaly(
    df: pd.DataFrame,
    col_anio: str = "año",
    col_temp: str = "temperatura",
) -> go.Figure:
    """
    Grafica la evolución de la anomalía térmica anual en estilo WGINOR.

    Parámetros
    ----------
    df : pd.DataFrame
        DataFrame de entrada con, al menos, las columnas de año y temperatura.
    col_anio : str
        Nombre de la columna que contiene el año.
    col_temp : str
        Nombre de la columna que contiene la temperatura.

    Lógica
    ------
    - Elimina filas sin año o sin temperatura.
    - Calcula la temperatura media anual.
    - Define una media climatológica global y computa la anomalía anual.
    - Calcula una tendencia suavizada mediante media móvil de 5 años.
    """
    if col_anio not in df.columns or col_temp not in df.columns:
        raise ValueError(
            f"El DataFrame debe contener las columnas '{col_anio}' y '{col_temp}'."
        )

    df_local = df[[col_anio, col_temp]].copy()
    df_local = df_local.dropna(subset=[col_anio, col_temp])

    # Asegurar tipo numérico para la temperatura y entero para el año
    df_local[col_temp] = pd.to_numeric(df_local[col_temp], errors="coerce")
    df_local[col_anio] = df_local[col_anio].astype(int)
    df_local = df_local.dropna(subset=[col_temp])

    # Media anual
    annual = (
        df_local.groupby(col_anio, as_index=False)[col_temp]
        .mean()
        .rename(columns={col_temp: "temp_media_anual"})
    )

    if annual.empty:
        raise ValueError("No hay datos suficientes para calcular anomalías térmicas.")

    # Media climatológica (periodo base completo)
    clim_mean = float(annual["temp_media_anual"].mean())
    annual["anomalía"] = annual["temp_media_anual"] - clim_mean

    # Tendencia suavizada: media móvil de 5 años centrada
    annual = annual.sort_values(col_anio)
    annual["tendencia_5a"] = (
        annual["anomalía"]
        .rolling(window=5, min_periods=1, center=True)
        .mean()
    )

    # Paleta de colores condicional (rojo para anomalías positivas, azul para negativas/cero)
    colors = [
        "#d62728" if val > 0 else "#1f77b4" for val in annual["anomalía"]
    ]

    fig = go.Figure()

    # Barras de anomalía anual
    fig.add_trace(
        go.Bar(
            x=annual[col_anio],
            y=annual["anomalía"],
            marker_color=colors,
            name="Anomalía anual",
        )
    )

    # Línea de tendencia suavizada (media móvil 5 años)
    fig.add_trace(
        go.Scatter(
            x=annual[col_anio],
            y=annual["tendencia_5a"],
            mode="lines",
            line=dict(color="black", width=3),  # type: ignore[arg-type,call]  # pyre-ignore
            name="Tendencia 5 años",
        )
    )

    # Línea horizontal de referencia (anomalía cero)
    fig.add_hline(y=0, line_width=1, line_color="black")

    fig.update_layout(
        title="Evolución de la Anomalía Térmica Anual (Estilo WGINOR)",
        template="simple_white",
        font=dict(family="Arial, sans-serif", size=14),  # type: ignore[arg-type,call]  # pyre-ignore
        xaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title="Año",
            showline=True,
            linecolor="lightgray",
            tickformat="d",
            dtick=1,
        ),
        yaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title="Anomalía Térmica (ºC)",
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        showlegend=False,
        hovermode="x unified",
    )

    return fig


def plot_wginor_anomaly(
    df: pd.DataFrame,
    col_anio: str,
    col_var: str,
    titulo: str,
    color_pos: str,
    color_neg: str,
    ylabel: str,
) -> go.Figure:
    """
    Gráfico WGINOR genérico de anomalías anuales para una variable.

    Parámetros
    ----------
    df : pd.DataFrame
        DataFrame con, al menos, columnas de año y variable.
    col_anio : str
        Nombre de la columna de año.
    col_var : str
        Nombre de la variable a analizar.
    titulo : str
        Título del gráfico.
    color_pos : str
        Color para anomalías positivas (> 0).
    color_neg : str
        Color para anomalías no positivas (<= 0).
    ylabel : str
        Etiqueta del eje Y.
    """
    if col_anio not in df.columns or col_var not in df.columns:
        raise ValueError(
            f"El DataFrame debe contener las columnas '{col_anio}' y '{col_var}'."
        )

    work = df[[col_anio, col_var]].copy()
    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work[col_var] = pd.to_numeric(work[col_var], errors="coerce")
    work = work.dropna(subset=[col_anio, col_var])

    if work.empty:
        raise ValueError("No hay datos válidos para calcular anomalías.")

    work[col_anio] = work[col_anio].astype(int)

    annual = (
        work.groupby(col_anio, as_index=False)[col_var]
        .mean()
        .rename(columns={col_var: "media_anual"})
        .sort_values(col_anio)
    )

    climatologia = float(annual["media_anual"].mean())
    annual["anomalia"] = annual["media_anual"] - climatologia
    annual["tendencia_3a"] = (
        annual["anomalia"].rolling(window=3, min_periods=1, center=True).mean()
    )

    bar_colors = [color_pos if v > 0 else color_neg for v in annual["anomalia"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=annual[col_anio],
            y=annual["anomalia"],
            marker_color=bar_colors,
            name="Anomalía anual",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=annual[col_anio],
            y=annual["tendencia_3a"],
            mode="lines",
            line=dict(color="black", width=2),  # type: ignore[arg-type,call]  # pyre-ignore
            name="Tendencia (MM 3 años)",
        )
    )
    fig.add_hline(y=0, line_width=1, line_color="black")

    fig.update_layout(
        template="simple_white",
        title=titulo,
        xaxis=dict(title="Año", tickformat="d", dtick=1),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(title=ylabel),  # type: ignore[arg-type,call]  # pyre-ignore
        showlegend=False,
    )

    return fig


def plot_hovmoller(
    df: pd.DataFrame,
    col_anio: str,
    col_profundidad: str,
    col_var: str,
    titulo: str,
    colorscale: str,
    thermocline_depth: Optional[float] = None,
    season_months: Optional[list] = None,
    col_estacion: Optional[str] = None,
    estacion_filtro: Optional[str] = None,
) -> go.Figure:
    """
    Diagrama de Hovmöller (mapa de calor) para profundidad vs tiempo.

    Parameters
    ----------
    thermocline_depth : float, optional
        Profundidad media de la termoclina; se anota con línea + texto.
    season_months : list[int], optional
        Meses (1-12) a incluir. None = todos. Ej: [6,7,8] = verano.
        Evita sesgo estacional si el muestreo no es uniforme por mes.
    col_estacion : str, optional
        Columna con el identificador de estación.
    estacion_filtro : str, optional
        Si se proporciona, filtra a esa estación antes de agregar.
        Evita mezcla espacial cuando hay varias estaciones en el radial.
    """
    for c in (col_anio, col_profundidad, col_var):
        if c not in df.columns:
            raise ValueError(f"No existe la columna requerida '{c}' en el DataFrame.")

    # Columnas a extraer (mínimas + opcionales para filtros)
    cols_needed = [col_anio, col_profundidad, col_var]
    fecha_candidates = ["fecha", "date", "fecha_muestreo", "datetime", "time"]
    lower_map = {c.lower(): c for c in df.columns}
    col_fecha_local: Optional[str] = next(
        (lower_map[c] for c in fecha_candidates if c in lower_map), None
    )
    if col_fecha_local and col_fecha_local not in cols_needed:
        cols_needed.append(col_fecha_local)
    if col_estacion and col_estacion in df.columns and col_estacion not in cols_needed:
        cols_needed.append(col_estacion)

    work = df[cols_needed].copy()
    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work[col_profundidad] = pd.to_numeric(work[col_profundidad], errors="coerce")
    work[col_var] = pd.to_numeric(work[col_var], errors="coerce")
    work = work.dropna(subset=[col_anio, col_profundidad, col_var])

    if work.empty:
        raise ValueError("No hay datos válidos para generar el diagrama de Hovmöller.")

    # Filtrar por estación (evita mezcla espacial entre estaciones del radial)
    if estacion_filtro and col_estacion and col_estacion in work.columns:
        work = work[work[col_estacion].astype(str) == str(estacion_filtro)]
        if work.empty:
            raise ValueError(f"No hay datos para la estación '{estacion_filtro}'.")

    # Filtrar por temporada (evita sesgo estacional si el muestreo no es uniforme)
    if season_months and col_fecha_local and col_fecha_local in work.columns:
        meses = pd.to_datetime(work[col_fecha_local], errors="coerce").dt.month
        work = work[meses.isin(season_months)]
        if work.empty:
            raise ValueError(
                f"No hay datos en los meses {season_months}. "
                "Prueba con otra temporada o selecciona 'Anual'."
            )

    # Gridding: profundidad en bins de 5 m
    work["prof_bin"] = (work[col_profundidad] // 5) * 5
    work[col_anio] = work[col_anio].astype(int)

    grouped = (
        work.groupby([col_anio, "prof_bin"], as_index=False)[col_var]
        .mean()
    )

    pivot_df = grouped.pivot(index="prof_bin", columns=col_anio, values=col_var)
    pivot_df = pivot_df.sort_index().sort_index(axis=1)

    n_vacias = int(pivot_df.isna().sum().sum())
    pct_vacias = 100.0 * n_vacias / pivot_df.size if pivot_df.size > 0 else 0.0

    # Título enriquecido con filtros activos
    titulo_completo = titulo
    if season_months:
        _m = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
              7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
        etiq = "-".join(_m.get(m, str(m)) for m in season_months)
        titulo_completo += f"  [{etiq}]"
    if estacion_filtro:
        titulo_completo += f"  · Est. {estacion_filtro}"

    fig = go.Figure(
        data=go.Heatmap(
            x=pivot_df.columns,
            y=pivot_df.index,
            z=pivot_df.values,
            colorscale=colorscale,
            connectgaps=False,   # NaN = celda en blanco honesta (sin interpolación)
            colorbar=dict(title=col_var),  # type: ignore[arg-type,call]  # pyre-ignore
            hovertemplate=(
                "Año: %{x}<br>Prof: %{y} m<br>"
                + col_var + ": %{z:.3f}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template="simple_white",
        title=dict(text=titulo_completo, font=dict(size=14)),  # type: ignore[arg-type,call]  # pyre-ignore
        xaxis=dict(title="Año", tickformat="d", dtick=1),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(autorange="reversed", title="Profundidad (m)"),  # type: ignore[arg-type,call]  # pyre-ignore
        margin=dict(r=120),   # espacio para la anotación de termoclina  # type: ignore[arg-type,call]  # pyre-ignore
    )

    if pct_vacias > 5:
        fig.add_annotation(
            text=f"⚠ {pct_vacias:.0f}% celdas sin datos",
            xref="paper", yref="paper", x=0.01, y=0.01,
            showarrow=False, font=dict(size=10, color="gray"),  # type: ignore[arg-type,call]  # pyre-ignore
        )

    # Anotación de la termoclina: shape + etiqueta en margen derecho
    if thermocline_depth is not None:
        x_min = int(pivot_df.columns.min())
        x_max = int(pivot_df.columns.max())
        fig.add_shape(
            type="line",
            x0=x_min, x1=x_max,
            y0=thermocline_depth, y1=thermocline_depth,
            line=dict(color="rgba(220, 170, 0, 0.85)", width=2, dash="dash"),  # type: ignore[arg-type,call]  # pyre-ignore
            xref="x", yref="y",
        )
        fig.add_annotation(
            x=x_max,
            y=thermocline_depth,
            text=f"  Termoclina<br>  (~{thermocline_depth:.0f} m)",
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(color="rgba(180, 120, 0, 1)", size=11, family="Arial"),  # type: ignore[arg-type,call]  # pyre-ignore
            xref="x", yref="y",
        )

    return fig



def plot_evolucion_temperatura_termoclina(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: Optional[str] = None,
) -> Tuple[go.Figure, Optional[float]]:
    """
    Evolución de la temperatura (y opcionalmente salinidad) a la profundidad de la termoclina.

    Para cada perfil, se calcula la profundidad del gradiente vertical térmico máximo
    y se toma la temperatura (y salinidad) a esa misma profundidad. Se agrega por año 
    (media entre perfiles) y se representa en doble eje (si aplica).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas de año, profundidad y temperatura.
    col_anio : str
        Nombre de la columna de año.
    col_prof : str
        Nombre de la columna de profundidad (m).
    col_temp : str
        Nombre de la columna de temperatura (ºC).
    col_sal : str, optional
        Nombre de la columna de salinidad (PSU). Si se provee, se grafica en doble eje.
    col_estacion : str, optional
        Si se proporciona, cada perfil es (año, estación); si no, perfil = año.

    Returns
    -------
    Tuple[go.Figure, Optional[float]]
        Figura Plotly y la profundidad media de la termoclina calculada (en metros),
        o None si no se pudo calcular.
    """
    cols_to_check = [col_anio, col_prof, col_temp]

    for c in cols_to_check:
        if c not in df.columns:
            raise ValueError(f"No existe la columna '{c}' en el DataFrame.")

    work = df[cols_to_check].copy()
    if col_estacion and col_estacion in df.columns:
        work[col_estacion] = df[col_estacion]
        
    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
    work[col_temp] = pd.to_numeric(work[col_temp], errors="coerce")
    
    work = work.dropna(subset=cols_to_check)

    if work.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No hay datos válidos para calcular la termoclina.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        fig.update_layout(template="simple_white", title="Evolución de la temperatura a la profundidad de la termoclina")
        return fig, None

    work[col_anio] = work[col_anio].astype(int)
    group_cols = [col_anio]
    if col_estacion and col_estacion in work.columns:
        group_cols.append(col_estacion)

    def _thermocline_temp_and_depth(grp: pd.DataFrame) -> Tuple:
        """Devuelve (temp, prof) para el perfil en termoclina."""
        grp = grp.sort_values(col_prof).drop_duplicates(subset=[col_prof])
        z = grp[col_prof].values
        t = grp[col_temp].values
        
        if len(z) < 2:
            return None, None
        dz = np.diff(z)
        dt = np.diff(t)
        if (dz <= 0).any():
            return None, None
            
        grad = dt / dz
        idx_max = int(np.nanargmax(np.abs(grad)))
        z_mid = float((z[idx_max] + z[idx_max + 1]) / 2.0)
        t_mid = float((t[idx_max] + t[idx_max + 1]) / 2.0)
        
        return t_mid, z_mid

    results = work.groupby(group_cols, group_keys=False).apply(
        lambda grp: pd.Series(
            _thermocline_temp_and_depth(grp),
            index=["temp_termoclina", "prof_termoclina"],
        )
    ).reset_index()

    results = results.dropna(subset=["temp_termoclina"])
    if results.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No se pudo calcular la temperatura a la profundidad de la termoclina (perfiles con pocos niveles).",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        fig.update_layout(template="simple_white", title="Evolución de la temperatura a la profundidad de la termoclina")
        return fig, None

    calc_cols = ["temp_termoclina", "prof_termoclina"]
    
    annual_agg = (
        results.groupby(col_anio, as_index=False)[calc_cols]
        .mean()
        .sort_values(col_anio)
    )

    mean_thermocline_depth = float(annual_agg["prof_termoclina"].mean()) if "prof_termoclina" in annual_agg.columns else None

    # Modo simple original
    y_max = float(annual_agg["temp_termoclina"].max())
    y_range = [0, round(y_max * 1.10, 1)]  # type: ignore[arg-type]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=annual_agg[col_anio], y=annual_agg["temp_termoclina"],
            mode="lines+markers", line=dict(color="#d62728", width=2.5),  # type: ignore[arg-type,call]  # pyre-ignore
            marker=dict(size=8), name="Temp. Termoclina",  # type: ignore[arg-type,call]  # pyre-ignore
            hovertemplate="Año: %{x}<br>Temperatura: %{y:.2f} ºC<extra></extra>",
        )
    )
    fig.update_layout(
        template="simple_white",
        title="Evolución de la temperatura a la profundidad de la termoclina",
        xaxis=dict(title="Año", tickformat="d", dtick=1),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(title="Temperatura (ºC)", range=y_range, showgrid=True, gridcolor="rgba(200, 200, 200, 0.3)"),  # type: ignore[arg-type,call]  # pyre-ignore
    )
        
    return fig, mean_thermocline_depth


def plot_perfil_vertical(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de perfil vertical CTD: profundidad vs temperatura y salinidad.

    Eje Y compartido (invertido): profundidad (superficie arriba).
    Eje X inferior: temperatura (rojo, baja opacidad para ver densidad/termoclina).
    Eje X superior: salinidad (azul, baja opacidad para ver haloclina).

    Parameters
    ----------
    df : pd.DataFrame
        Debe contener al menos las columnas 'profundidad', 'temperatura' y 'salinidad'
        (nombres en minúsculas tras normalización).

    Returns
    -------
    go.Figure
        Figura Plotly con doble eje X y Y invertido.
    """
    cols_lower = {str(c).lower().strip(): c for c in df.columns}
    col_depth = next((cols_lower[k] for k in ("profundidad", "depth") if k in cols_lower), None)
    col_temp = next((cols_lower[k] for k in ("temperatura", "temp", "temp_c") if k in cols_lower), None)
    col_sal = next((cols_lower[k] for k in ("salinidad", "salinity", "sal") if k in cols_lower), None)

    if not col_depth or not col_temp or not col_sal:
        raise ValueError(
            "El DataFrame debe contener columnas de profundidad, temperatura y salinidad."
        )

    data = df[[col_depth, col_temp, col_sal]].copy()
    data = data.dropna(subset=[col_depth, col_temp, col_sal])
    data[col_temp] = pd.to_numeric(data[col_temp], errors="coerce")
    data[col_sal] = pd.to_numeric(data[col_sal], errors="coerce")
    data[col_depth] = pd.to_numeric(data[col_depth], errors="coerce")
    data = data.dropna(subset=[col_depth, col_temp, col_sal])

    if data.empty:
        raise ValueError("No quedan filas válidas de profundidad/temperatura/salinidad.")

    fig = go.Figure()

    # Eje X principal (abajo): temperatura — rojo, opacidad baja
    fig.add_trace(
        go.Scatter(
            x=data[col_temp],
            y=data[col_depth],
            mode="markers",
            marker=dict(color="#d62728", opacity=0.15, size=4),  # type: ignore[arg-type,call]  # pyre-ignore
            name="Temperatura",
            xaxis="x",
            yaxis="y",
        )
    )

    # Eje X secundario (arriba): salinidad — azul marino, opacidad baja
    fig.add_trace(
        go.Scatter(
            x=data[col_sal],
            y=data[col_depth],
            mode="markers",
            marker=dict(color="#1f77b4", opacity=0.15, size=4),  # type: ignore[arg-type,call]  # pyre-ignore
            name="Salinidad",
            xaxis="x2",
            yaxis="y",
        )
    )

    fig.update_layout(
        template="simple_white",
        title="Patrones de Perfil Vertical (Termoclina y Haloclina)",
        font=dict(family="Arial, sans-serif", size=14),  # type: ignore[arg-type,call]  # pyre-ignore
        xaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title="Temperatura (°C)",
            side="bottom",
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        xaxis2=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title="Salinidad (PSU)",
            side="top",
            overlaying="x",
            anchor="y",
            showline=True,
            linecolor="lightgray",
            showgrid=False,
        ),
        yaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title="Profundidad (m)",
            autorange="reversed",
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),  # type: ignore[arg-type,call]  # pyre-ignore
        hovermode="closest",
    )

    return fig


def compute_data_metadata(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_fecha: Optional[str] = None,
    col_estacion: Optional[str] = None,
) -> dict:
    """
    Calcula indicadores de calidad del muestreo CTD.

    Returns
    -------
    dict con claves:
        n_registros : int
        n_perfiles_estimados : int  (pares únicos fecha×estación o fechas únicas)
        campanas_por_anio : dict[int, int]
        meses_muestreados : list[int]  (meses con al menos 1 registro)
        estaciones : list[str]
        resolucion_ctd_mediana_m : float | None
        cobertura_temporal : str  ("YYYY–YYYY")
        datos_procesados : bool   (True si el CSV se llama *processed*)
        nota_resolucion : str
    """
    meta: dict = {}

    # --- Registros totales ---
    meta["n_registros"] = len(df)

    # --- Cobertura temporal ---
    anos = df[col_anio].dropna()
    try:
        anos_int = pd.to_numeric(anos, errors="coerce").dropna().astype(int)
        meta["cobertura_temporal"] = (
            f"{int(anos_int.min())}–{int(anos_int.max())}"
            if len(anos_int) > 1 else str(int(anos_int.iloc[0]))
        )
    except Exception:
        meta["cobertura_temporal"] = "desconocida"

    # --- Estaciones ---
    if col_estacion and col_estacion in df.columns:
        meta["estaciones"] = sorted(df[col_estacion].dropna().astype(str).unique().tolist())
    else:
        meta["estaciones"] = ["no identificadas"]

    # --- Perfiles y campañas por año ---
    if col_fecha and col_fecha in df.columns:
        fechas = pd.to_datetime(df[col_fecha], errors="coerce")
        df_tmp = df.copy()
        df_tmp["_fecha_norm"] = fechas.dt.date
        df_tmp["_anio"] = pd.to_numeric(df[col_anio], errors="coerce").astype("Int64")

        # Perfil = fecha única (× estación si existe)
        perfil_cols = ["_fecha_norm"]
        if col_estacion and col_estacion in df_tmp.columns:
            perfil_cols.append(col_estacion)
        meta["n_perfiles_estimados"] = int(df_tmp[perfil_cols].drop_duplicates().shape[0])

        campanas = (
            df_tmp.groupby("_anio")[perfil_cols]
            .apply(lambda g: g.drop_duplicates().shape[0])
            .to_dict()  # type: ignore[arg-type,call]  # pyre-ignore
        )
        meta["campanas_por_anio"] = {int(k): int(v) for k, v in campanas.items() if pd.notna(k)}

        meses = fechas.dt.month.dropna().unique().tolist()
        meta["meses_muestreados"] = sorted(int(m) for m in meses)
    else:
        meta["n_perfiles_estimados"] = None
        meta["campanas_por_anio"] = {}
        meta["meses_muestreados"] = []

    # --- Resolución vertical del CTD ---
    try:
        import numpy as np
        prof_numeric = pd.to_numeric(df[col_prof], errors="coerce").dropna().sort_values()
        diffs = prof_numeric.diff().dropna()
        diffs_pos = diffs[diffs > 0]
        meta["resolucion_ctd_mediana_m"] = float(np.median(diffs_pos)) if len(diffs_pos) > 0 else None
        meta["nota_resolucion"] = (
            f"Resolución vertical estimada: ~{meta['resolucion_ctd_mediana_m']:.1f} m "
            "(mediana de Δz entre registros consecutivos con profundidad creciente). "
            "⚠ Pendiente confirmar con el responsable del CTD."
        ) if meta["resolucion_ctd_mediana_m"] else "No se pudo estimar la resolución vertical."
    except Exception:
        meta["resolucion_ctd_mediana_m"] = None
        meta["nota_resolucion"] = "No se pudo estimar la resolución vertical."

    meta["datos_procesados"] = True  # Flag fijo; el CSV proviene de sireno_..._processed.csv

    return meta


def plot_sampling_heatmap(
    df: pd.DataFrame,
    col_anio: str,
    col_fecha: str,
    col_estacion: Optional[str] = None,
) -> go.Figure:
    """
    Heatmap de año × mes mostrando el nº de perfiles CTD por celda.

    Permite detectar de un vistazo el sesgo estacional (¿hay meses sin datos
    en ciertos años?) y la cobertura interanual del muestreo.
    """
    if col_fecha not in df.columns or col_anio not in df.columns:
        raise ValueError("Se requieren columnas de año y fecha para el heatmap de muestreo.")

    tmp = df.copy()
    tmp["_anio"] = pd.to_numeric(tmp[col_anio], errors="coerce").astype("Int64")
    fechas = pd.to_datetime(tmp[col_fecha], errors="coerce")
    tmp["_mes"] = fechas.dt.month
    tmp["_fecha_d"] = fechas.dt.date

    # Contar perfiles únicos por (año, mes)
    perfil_cols = ["_anio", "_mes", "_fecha_d"]
    if col_estacion and col_estacion in tmp.columns:
        perfil_cols.append(col_estacion)

    counts = (
        tmp[perfil_cols]
        .drop_duplicates()
        .groupby(["_anio", "_mes"])
        .size()
        .reset_index(name="n_perfiles")
    )
    counts = counts.dropna(subset=["_anio", "_mes"])
    counts["_anio"] = counts["_anio"].astype(int)
    counts["_mes"] = counts["_mes"].astype(int)

    pivot = counts.pivot(index="_mes", columns="_anio", values="n_perfiles")
    pivot = pivot.sort_index().sort_index(axis=1)

    meses_labels = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                    7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    y_labels = [meses_labels.get(m, str(m)) for m in pivot.index]

    fig = go.Figure(
        data=go.Heatmap(
            x=pivot.columns,
            y=y_labels,
            z=pivot.values,
            colorscale=[[0,"#f7f7f7"],[0.5,"#41b6c4"],[1,"#081d58"]],
            showscale=True,
            colorbar=dict(title="N perfiles"),  # type: ignore[arg-type,call]  # pyre-ignore
            hovertemplate="Año: %{x}<br>Mes: %{y}<br>Perfiles: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        template="simple_white",
        title=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            text="Cobertura del muestreo CTD por año y mes<br>"
                 "<sup>Celdas en blanco = sin muestreo ese mes/año</sup>",
            font=dict(size=13),  # type: ignore[arg-type,call]  # pyre-ignore
        ),
        xaxis=dict(title="Año", tickformat="d", dtick=1),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(title="Mes", autorange="reversed"),  # type: ignore[arg-type,call]  # pyre-ignore
        height=350,
    )
    return fig


def plot_wginor_dual_anomaly(
    df: pd.DataFrame,
    col_anio: str,
    col_temp: str,
    col_sal: str,
    label_temp: str = "Temperatura",
    label_sal: str = "Salinidad",
    titulo: str = "Anomalías Anuales de Temperatura y Salinidad",
) -> go.Figure:
    """
    Gráfico dual de anomalías anuales: temperatura (eje Y izquierdo)
    y salinidad (eje Y derecho) en la misma figura.

    Cada variable se normaliza a su propia media climatológica, por lo que
    los ejes son independientes pero comparables en forma (no en magnitud).

    Interpretación
    --------------
    - Anomalía T positiva + anomalía S negativa → agua superficial cálida y fresca
      (dominancia de agua superficial atlántica, baja productividad).
    - Anomalía T negativa + anomalía S positiva → afloramiento de ENACW,
      agua fría y salada, alta productividad potencial.
    - Correlación positiva T-S → entrada de NAC (agua cálida y salada).
    """
    for col in (col_anio, col_temp, col_sal):
        if col not in df.columns:
            raise ValueError(f"Columna '{col}' no encontrada en el DataFrame.")

    def _anomaly_series(df: pd.DataFrame, col_anio: str, col_var: str) -> pd.DataFrame:
        work = df[[col_anio, col_var]].copy()
        work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
        work[col_var] = pd.to_numeric(work[col_var], errors="coerce")
        work = work.dropna()
        work[col_anio] = work[col_anio].astype(int)
        annual = (
            work.groupby(col_anio, as_index=False)[col_var]
            .mean()
            .rename(columns={col_var: "media"})
            .sort_values(col_anio)
        )
        
        # Calcular media climatológica (2001-2009)
        base_period = annual[annual[col_anio].between(2001, 2009)]
        baseline_mean = base_period["media"].mean()
        if pd.isna(baseline_mean):
            baseline_mean = annual["media"].mean()

        annual["anomalia"] = annual["media"] - baseline_mean
        annual["tendencia"] = (
            annual["anomalia"].rolling(window=3, min_periods=1, center=True).mean()
        )
        return annual

    anom_t = _anomaly_series(df, col_anio, col_temp)
    anom_s = _anomaly_series(df, col_anio, col_sal)

    colors_t = ["#d62728" if v > 0 else "#ff9896" for v in anom_t["anomalia"]]
    colors_s = ["#1f77b4" if v > 0 else "#aec7e8" for v in anom_s["anomalia"]]

    fig = go.Figure()

    # Barras de temperatura (eje Y1)
    fig.add_trace(go.Bar(
        x=anom_t[col_anio], y=anom_t["anomalia"],
        marker_color=colors_t, name=f"Anomalía {label_temp}",
        yaxis="y1", opacity=0.85, offsetgroup="1",
    ))
    fig.add_trace(go.Scatter(
        x=anom_t[col_anio], y=anom_t["tendencia"],
        mode="lines", line=dict(color="#d62728", width=2.5, dash="solid"),  # type: ignore[arg-type,call]  # pyre-ignore
        name=f"Tendencia {label_temp} (MM3)", yaxis="y1",
    ))

    # Barras de salinidad (eje Y2)
    fig.add_trace(go.Bar(
        x=anom_s[col_anio], y=anom_s["anomalia"],
        marker_color=colors_s, name=f"Anomalía {label_sal}",
        yaxis="y2", opacity=0.85, offsetgroup="2",
    ))
    fig.add_trace(go.Scatter(
        x=anom_s[col_anio], y=anom_s["tendencia"],
        mode="lines", line=dict(color="#1f77b4", width=2.5, dash="dot"),  # type: ignore[arg-type,call]  # pyre-ignore
        name=f"Tendencia {label_sal} (MM3)", yaxis="y2",
    ))

    fig.add_hline(y=0, line_width=1, line_color="black", line_dash="solid")

    fig.update_layout(
        template="simple_white",
        title=dict(text=titulo, font=dict(size=14)),  # type: ignore[arg-type,call]  # pyre-ignore
        barmode="group",
        xaxis=dict(title="Año", tickformat="d", dtick=1),  # type: ignore[arg-type,call]  # pyre-ignore
        yaxis=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title=f"Anomalía {label_temp} (ºC)",
            side="left",
            showgrid=True, gridcolor="rgba(200,200,200,0.3)",
        ),
        yaxis2=dict(  # type: ignore[arg-type,call]  # pyre-ignore
            title=f"Anomalía {label_sal} (PSU)",
            side="right",
            overlaying="y",
            showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),  # type: ignore[arg-type,call]  # pyre-ignore
        hovermode="x unified",
    )
    return fig


def _load_local_csv_if_available() -> Optional[pd.DataFrame]:

    """
    Intenta cargar el CSV procesado del flujo Sireno Gijón CTD.
    """
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data" / "processed"

    candidates = [
        "sireno_gijon_ctd_processed.csv",
        "sireno_gijon_ctd_forecast.csv",
    ]

    for name in candidates:
        csv_path = data_dir / name
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                return df
            except Exception:
                # Si falla la lectura de un candidato, probamos el siguiente.
                continue
    return None


def _generate_dummy_data() -> pd.DataFrame:
    """
    Genera datos dummy mínimos para testear el módulo sin Streamlit.

    Crea una serie temporal mensual 2002–2019 con patrón estacional simple
    y ligera tendencia positiva.
    """
    rng = pd.date_range(start="2002-01-01", end="2019-12-31", freq="MS")
    n = len(rng)

    # Patrón estacional: seno anual + ruido blanco
    import numpy as np

    base = 14.0
    trend = 0.02  # ºC por año
    years_since_start = (rng.year - rng.year.min()).astype(float)
    seasonal = 3.0 * np.sin(2 * np.pi * (rng.month - 1) / 12.0)
    noise = np.random.default_rng(42).normal(0, 0.4, size=n)

    temp = base + trend * years_since_start + seasonal + noise

    return pd.DataFrame({"Fecha": rng, "Temperatura": temp})


def plot_temp_5m_anual(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    output_dir: Optional[Path] = None,
) -> go.Figure:
    """
    Evolución de la temperatura media anual a 5 m de profundidad,
    desglosada por estación (1, 2 y 3).

    Metodología
    -----------
    - Se calcula T(5 m) por perfil (cast) usando:
      - valor exacto a 5 m si existe
      - si 5 m cae entre dos niveles, interpolación lineal en profundidad
      - si 5 m cae fuera del rango del perfil, se descarta ese perfil
    - Se agrega por (año, estación): media de T(5 m).
    - La banda de incertidumbre (si hay n>=2) es el IC 95% de la media anual
      por estación (t de Student cuando está disponible; si no, aproximación normal).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame limpio con columnas de año, profundidad, temperatura y estación.
    col_anio : str
        Nombre de la columna de año.
    col_prof : str
        Nombre de la columna de profundidad (m).
    col_temp : str
        Nombre de la columna de temperatura (ºC).
    col_estacion : str
        Nombre de la columna de estación (valores 1, 2, 3).
    output_dir : Path, optional
        Si se proporciona, guarda la figura como PNG en esa carpeta.

    Returns
    -------
    go.Figure
    """
    TARGET_DEPTH = 5.0
    ESTACIONES_VALIDAS = [1, 2, 3]

    # --- Validación ---
    for c in (col_anio, col_prof, col_temp, col_estacion):
        if c not in df.columns:
            raise ValueError(f"Columna requerida '{c}' no existe en el DataFrame.")

    col_cast: str | None = "acronimo" if "acronimo" in df.columns else None
    cols = [col_anio, col_prof, col_temp, col_estacion]
    if col_cast is not None:
        cols.append(col_cast)

    work = df[cols].copy()
    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
    work[col_temp] = pd.to_numeric(work[col_temp], errors="coerce")
    work[col_estacion] = pd.to_numeric(work[col_estacion], errors="coerce")
    work = work.dropna(subset=[col_prof, col_temp, col_estacion])

    # Excluir estación 4 (por si acaso llegara en el df)
    work = work[work[col_estacion].isin(ESTACIONES_VALIDAS)]

    if work.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No hay registros válidos para calcular T(5 m).",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        fig.update_layout(template="simple_white",
                          title="Temperatura media anual a 5 m — sin datos")
        return fig

    def _parse_year_from_acronimo(s: object) -> float:
        """
        Regla: los 4 últimos dígitos son YYMM (p.e. RADGIJ0902 => 2009-02).
        """
        try:
            txt = str(s).strip()
        except Exception:
            return float("nan")
        if len(txt) < 4 or not txt[-4:].isdigit():
            return float("nan")
        yy = int(txt[-4:-2])
        # Convención: 00-79 => 2000-2079; 80-99 => 1980-1999 (ajustable)
        return float(2000 + yy) if yy <= 79 else float(1900 + yy)

    if col_cast is not None and work[col_anio].isna().any():
        filled = work[col_cast].map(_parse_year_from_acronimo)
        work[col_anio] = work[col_anio].fillna(filled)

    work[col_anio] = pd.to_numeric(work[col_anio], errors="coerce")
    work = work.dropna(subset=[col_anio])
    work[col_anio] = work[col_anio].astype(int)
    work[col_estacion] = work[col_estacion].astype(int)

    def _temp_at_depth(profile: pd.DataFrame) -> float:
        """Devuelve T a TARGET_DEPTH para un perfil; NaN si no es posible."""
        prof = pd.to_numeric(profile[col_prof], errors="coerce")
        temp = pd.to_numeric(profile[col_temp], errors="coerce")
        mask = prof.notna() & temp.notna()
        if not mask.any():
            return float("nan")
        prof = prof[mask]
        temp = temp[mask]

        # Promediar si hay profundidades repetidas
        dft = pd.DataFrame({"z": prof.values, "t": temp.values}).groupby("z", as_index=False)["t"].mean()
        if dft.empty:
            return float("nan")
        z = dft["z"].to_numpy(dtype=float)
        t = dft["t"].to_numpy(dtype=float)

        order = np.argsort(z)
        z = z[order]
        t = t[order]

        z_min = float(z[0])
        z_max = float(z[-1])
        if TARGET_DEPTH < z_min or TARGET_DEPTH > z_max:
            return float("nan")

        # np.interp devuelve el valor exacto si TARGET_DEPTH coincide con z
        return float(np.interp(TARGET_DEPTH, z, t))

    # Calcular T(5 m) por perfil/cast (si hay acronimo) o por (año, estación) si no.
    group_keys = [col_estacion]
    if col_cast is not None:
        group_keys.append(col_cast)
    else:
        group_keys.append(col_anio)

    per_cast = (
        work.groupby(group_keys, as_index=False)
        .apply(lambda g: pd.Series({col_anio: int(g[col_anio].mode().iat[0]), "temp_5m": _temp_at_depth(g)}))
        .reset_index(drop=True)
    )

    per_cast = per_cast.dropna(subset=["temp_5m"])
    if per_cast.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No se pudo estimar T(5 m) en ningún perfil (5 m fuera de rango o datos insuficientes).",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        fig.update_layout(template="simple_white",
                          title="Temperatura media anual a 5 m — sin datos")
        return fig

    # Agregar por (año, estación): media + IC95
    def _tcrit_975(dfree: int) -> float:
        if dfree <= 0:
            return float("nan")
        try:
            from scipy.stats import t as student_t  # type: ignore
            return float(student_t.ppf(0.975, dfree))
        except Exception:
            return 1.96  # aproximación normal

    agg = (
        per_cast.groupby([col_anio, col_estacion], as_index=False)["temp_5m"]
        .agg(n="count", mean="mean", std=lambda x: float(np.std(x.to_numpy(dtype=float), ddof=1)) if len(x) >= 2 else float("nan"))
        .sort_values([col_estacion, col_anio])
    )
    agg["sem"] = agg["std"] / np.sqrt(agg["n"].astype(float))
    agg["tcrit"] = agg["n"].apply(lambda n: _tcrit_975(int(n) - 1) if int(n) >= 2 else float("nan"))
    agg["ci_half"] = agg["tcrit"] * agg["sem"]
    agg["lower"] = agg["mean"] - agg["ci_half"]
    agg["upper"] = agg["mean"] + agg["ci_half"]

    # --- Figura ---
    COLORS = {1: "#1f77b4", 2: "#2ca02c", 3: "#d62728"}
    NAMES  = {1: "Estación 1", 2: "Estación 2", 3: "Estación 3"}

    fig = go.Figure()

    for est in ESTACIONES_VALIDAS:
        sub = agg[agg[col_estacion] == est].copy()
        if sub.empty:
            continue
        sub = sub.sort_values(col_anio)

        # Banda IC95 (si hay n>=2)
        band_ok = sub["lower"].notna() & sub["upper"].notna()
        if band_ok.any():
            x_band = sub.loc[band_ok, col_anio]
            lower = sub.loc[band_ok, "lower"]
            upper = sub.loc[band_ok, "upper"]
            fig.add_trace(
                go.Scatter(
                    x=x_band,
                    y=lower,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"{NAMES[est]} IC95 (inf.)",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=x_band,
                    y=upper,
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor=f"rgba{tuple(int(COLORS[est].lstrip('#')[i:i+2], 16) for i in (0,2,4)) + (0.18,)}",
                    showlegend=True,
                    name=f"{NAMES[est]} IC95",
                    hovertemplate=(
                        f"<b>{NAMES[est]} IC95</b><br>"
                        "Año: %{x}<br>"
                        "IC95 sup.: %{y:.2f} ºC<extra></extra>"
                    ),
                )
            )

        fig.add_trace(
            go.Scatter(
                x=sub[col_anio],
                y=sub["mean"],
                mode="lines+markers",
                name=NAMES[est],
                line=dict(color=COLORS[est], width=2.5),
                marker=dict(size=8, color=COLORS[est]),
                customdata=np.stack([sub["n"]], axis=-1),
                hovertemplate=(
                    f"<b>{NAMES[est]}</b><br>"
                    "Año: %{x}<br>"
                    "Temp(5 m): %{y:.2f} ºC<br>"
                    "n perfiles: %{customdata[0]}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        template="simple_white",
        title=dict(
            text="Temperatura media anual a 5 m (línea) + IC 95% (banda) — Radial Gijón",
            font=dict(size=14),
        ),
        xaxis=dict(
            title="Año",
            tickformat="d",
            dtick=1,
            showline=True,
            linecolor="lightgray",
        ),
        yaxis=dict(
            title="Temperatura media (ºC)",
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
        height=420,
    )

    # --- Guardar PNG ---
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        png_path = output_dir / "temp_5m_anual_gijon.png"
        try:
            fig.write_image(str(png_path), width=1200, height=500, scale=2)
        except Exception as exc:
            import warnings
            warnings.warn(
                f"No se pudo guardar el PNG (¿kaleido instalado?): {exc}",
                stacklevel=2,
            )

    return fig


def plot_temp_5m_anual_estaciones_con_ic_global(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    estaciones_visibles: Optional[list[int]] = None,
    nivel_profundidad: str = "superficie",
    mostrar_valor_termoclina: bool = False,
    forecast_years: int = 0,
    forecast_degree: int = 2,
    forecast_bootstrap: int = 400,
    forecast_show_ci: bool = True,
) -> go.Figure:
    """
    T(5 m) media anual por estación (líneas) + IC95 por estación (banda).

    - Líneas: media anual de T(5 m) por estación (1,2,3).
    - Banda: IC95 de la media anual por estación (solo si n_perfiles >= 2).

    Notas:
    - T(5 m) se estima por perfil/cast (acronimo) mediante interpolación lineal en profundidad.
    - Si `scipy` está disponible se usa t de Student para el crítico; si no, 1.96.
    - Forecast opcional (estilo WGINOR): zona de forecast sombreada + extensión
      discontinua. El ajuste es un polinomio (grado configurable) por estación.
    """
    ESTACIONES_VALIDAS = [1, 2, 3]
    estaciones_visibles = estaciones_visibles or ESTACIONES_VALIDAS
    nivel_map = {
        "superficie": ("temp_superficie", "Superficie (5 m)"),
        "termoclina": ("temp_termoclina", "Termoclina"),
        "fondo": ("temp_fondo", "Fondo béntico"),
    }
    nivel_key = str(nivel_profundidad).strip().lower()
    if nivel_key not in nivel_map:
        raise ValueError(
            "nivel_profundidad no válido. Usa: 'superficie', 'termoclina' o 'fondo'."
        )
    level_col, level_label = nivel_map[nivel_key]

    # Datos ya pre-agregados en capa de aplicación web para mejorar rendimiento en RAM
    by_station = df.copy()

    # Rango Y global (histórico): blindado con IC95 de las 3 estaciones.
    # No incluye forecast para evitar que la proyección distorsione la escala.
    hist_mask = by_station["mean"].notna()
    global_y_min = float(by_station.loc[hist_mask, "mean"].min()) if hist_mask.any() else 0.0
    global_y_max = float(by_station.loc[hist_mask, "mean"].max()) if hist_mask.any() else 1.0

    ic_mask = by_station["lower"].notna() & by_station["upper"].notna()
    if ic_mask.any():
        global_y_min = min(global_y_min, float(by_station.loc[ic_mask, "lower"].min()))
        global_y_max = max(global_y_max, float(by_station.loc[ic_mask, "upper"].max()))

    y_span = global_y_max - global_y_min
    y_pad = 0.10 * y_span if y_span > 0 else 0.5
    y_range = [global_y_min - y_pad, global_y_max + y_pad]

    # Colores y nombres
    # Estética solicitada:
    #   - Estación 1 (Costa): rojizo
    #   - Estación 2 (Plataforma): amarillo
    #   - Estación 3 (Talud): azul
    COLORS = {
        1: "#d62728",  # rojo suave
        2: "#ffbf00",  # amarillo dorado
        3: "#1f77b4",  # azul
    }
    NAMES = {1: "Estación 1", 2: "Estación 2", 3: "Estación 3"}

    fig = go.Figure()

    # ------------------------------------------------------------------
    # Forecast estilo WGINOR (opcional)
    # ------------------------------------------------------------------
    def _auto_forecast_horizon(n_years: int) -> int:
        """
        Heurística conservadora: el horizonte crece con la longitud de la serie,
        acotado para evitar sobre-interpretación.
        """
        if n_years < 8:
            return 0
        if n_years < 12:
            return 2
        if n_years < 18:
            return 3
        if n_years < 25:
            return 4
        return 5

    def _poly_forecast_line(
        years: np.ndarray,
        values: np.ndarray,
        years_future: np.ndarray,
        degree: int,
    ) -> np.ndarray:
        """
        Ajuste polinómico (grado `degree`) y predicción puntual para años futuros.

        Devuelve:
          yhat_future (solo valores medios; sin IC95 ni bootstrap).
        """
        if degree < 1:
            degree = 1
        degree = int(min(degree, max(1, len(years) - 1)))

        x = years.astype(float)
        y = values.astype(float)
        xf = years_future.astype(float)

        # Centrado para estabilidad numérica
        x0 = float(np.mean(x))
        xc = x - x0
        xfc = xf - x0

        coef = np.polyfit(xc, y, deg=degree)
        yhat_f = np.polyval(coef, xfc)
        return yhat_f

    # Interpretación de forecast_years:
    # - 0  => sin forecast
    # - -1 => horizonte automático según nº de años disponibles
    # - >0 => horizonte fijo
    if forecast_years == -1:
        # Conservador: usar el mínimo nº de años entre estaciones visibles
        counts = []
        for est in estaciones_visibles:
            yrs = by_station.loc[by_station[col_estacion] == est, col_anio].dropna().astype(int).unique()
            counts.append(int(len(yrs)))
        n_years_min = int(min(counts)) if counts else 0
        forecast_years = _auto_forecast_horizon(n_years_min)
    forecast_years = int(max(0, forecast_years))

    valid_hist = by_station[by_station["mean"].notna()]
    if valid_hist.empty:
        max_hist_year = int(by_station[col_anio].max())
    else:
        max_hist_year = int(valid_hist[col_anio].max())
    future_years = (
        np.arange(max_hist_year + 1, max_hist_year + forecast_years + 1, dtype=int)
        if forecast_years > 0
        else np.array([], dtype=int)
    )

    if forecast_years > 0:
        # Solo línea vertical de demarcación en el último año histórico
        fig.add_vline(
            x=max_hist_year,
            line=dict(color="#7f7f7f", width=1.5, dash="dash"),
            annotation_text="Proyección \u2192",
            annotation_position="top right",
        )

    # Bandas + líneas por estación (la banda sigue a su estación)
    for est in ESTACIONES_VALIDAS:
        if est not in estaciones_visibles:
            continue
        sub = by_station[by_station[col_estacion] == est].sort_values(col_anio).copy()
        if sub.empty:
            continue

        band_ok = sub["lower"].notna() & sub["upper"].notna() & (sub["n"] >= 2)
        if band_ok.any():
            x_band = sub.loc[band_ok, col_anio]
            lower = sub.loc[band_ok, "lower"]
            upper = sub.loc[band_ok, "upper"]

            rgb = tuple(int(COLORS[est].lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
            fillcolor = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.18)"

            fig.add_trace(
                go.Scatter(
                    x=x_band,
                    y=lower,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"{NAMES[est]} IC95 (inf.)",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=x_band,
                    y=upper,
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor=fillcolor,
                    showlegend=True,
                    name=f"{NAMES[est]} IC95",
                    hoverinfo="skip",
                )
            )

        fig.add_trace(
            go.Scatter(
                x=sub[col_anio],
                y=sub["mean"],
                mode="lines+markers+text" if (nivel_key == "termoclina" and mostrar_valor_termoclina) else "lines+markers",
                connectgaps=False,
                name=NAMES[est],
                line=dict(color=COLORS[est], width=2.5),
                marker=dict(size=7, color=COLORS[est]),
                text=(
                    sub["prof_termoclina_media"].map(lambda v: f"{float(v):.1f} m" if pd.notna(v) else "").tolist()
                    if (nivel_key == "termoclina" and mostrar_valor_termoclina)
                    else None
                ),
                textposition="top center",
                customdata=(
                    sub["prof_termoclina_media"].to_numpy(dtype=float)
                    if nivel_key == "termoclina"
                    else np.stack([sub["n"]], axis=-1)
                ),
                hovertemplate="Temperatura: %{y:.2f} ºC<extra></extra>",
            )
        )

        # Forecast por estación: extensión discontinua (sin banda IC95)
        if forecast_years > 0 and len(sub) >= 4:
            # Usar solo años con media válida para entrenar la tendencia
            hist_ok = sub["mean"].notna()
            years_hist = sub.loc[hist_ok, col_anio].to_numpy(dtype=int)
            vals_hist = sub.loc[hist_ok, "mean"].to_numpy(dtype=float)
            if len(years_hist) < 2:
                continue

            # Predicción para años futuros
            yhat_future = _poly_forecast_line(
                years_hist,
                vals_hist,
                future_years,
                degree=forecast_degree,
            )

            # Anclaje: primer punto del forecast en el último año real
            last_year = int(years_hist.max())
            last_val = float(vals_hist[years_hist.argmax()])
            x_fore = np.concatenate([[last_year], future_years])
            y_fore = np.concatenate([[last_val], yhat_future])

            # Línea punteada de forecast (media predicha) — mismo color que la estación
            fig.add_trace(
                go.Scatter(
                    x=x_fore,
                    y=y_fore,
                    mode="lines",
                    line=dict(color=COLORS[est], width=2.2, dash="dot"),
                    name=f"{NAMES[est]} Forecast",
                    showlegend=False,
                    hovertemplate="Temperatura: %{y:.2f} ºC<extra></extra>",
                )
            )

    fig.update_layout(
        template="simple_white",
        title=dict(text=f"Evolución de la Temperatura Media Anual - {level_label}", font=dict(size=14)),
        xaxis=dict(title="Año", tickformat="d", dtick=1, showline=True, linecolor="lightgray"),
        yaxis=dict(
            title="Temperatura (ºC)",
            range=y_range,
            showline=True,
            linecolor="lightgray",
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=480,
    )
    return fig


def plot_hovmoller_termoclina(
    df: pd.DataFrame,
    estado_slider: str,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    resolucion: str = "Media Mensual (Estacionalidad)",
) -> go.Figure:
    """
    Hovmöller de temperatura (fecha de campaña vs profundidad) con cobertura total.

    Reglas:
    - Sin recorte de profundidad: usa todo el rango histórico disponible.
    - Paso 2/3/4: figura única por estación.
    - Paso 5: comparativa en 3 subplots horizontales con eje Y compartido.
    """
    # Datos ya pre-agregados en capa de aplicación web para mejorar rendimiento en RAM
    # - Anual: df tiene [col_anio, "prof_bin", col_estacion, col_temp]
    # - Mensual: df tiene ["fecha", "prof_bin", col_estacion, col_temp] (tiempo continuo MS)
    work = df.copy()

    if work.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No hay datos válidos para generar el Hovmöller.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        fig.update_layout(template="simple_white", title="Evolución termoclina (Hovmöller)")
        return fig

    station_map = {
        "2. Costa (E1)": [1],
        "3. Plataforma (E2)": [2],
        "4. Talud (E3)": [3],
        "5. Comparativa": [1, 2, 3],
    }
    stations = station_map.get(estado_slider, [])
    if not stations:
        fig = go.Figure()
        fig.add_annotation(
            text="Seleccione una Estación para ver el Hovmöller.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=15, color="#6b7280"),
        )
        fig.update_layout(
            template="simple_white",
            title="Evolución termoclina (Hovmöller)",
            height=500,
        )
        return fig

    def _build_station_grid_monthly(est: int) -> pd.DataFrame:
        """
        Construye una matriz perfecta (prof_bin × fecha) y rellena huecos pequeños
        con interpolación 2D (profundidad y tiempo).
        """
        if "fecha" not in work.columns:
            return pd.DataFrame()
        sub = work[work[col_estacion] == est].copy()
        if sub.empty:
            return pd.DataFrame()
        sub["fecha"] = pd.to_datetime(sub["fecha"], errors="coerce")
        sub["prof_bin"] = pd.to_numeric(sub["prof_bin"], errors="coerce")
        sub[col_temp] = pd.to_numeric(sub[col_temp], errors="coerce")
        sub = sub.dropna(subset=["fecha", "prof_bin", col_temp])
        if sub.empty:
            return pd.DataFrame()

        # Asegurar malla mensual continua (MS) y profundidad regular 1 m
        t0 = sub["fecha"].min()
        t1 = sub["fecha"].max()
        full_t = pd.date_range(start=t0, end=t1, freq="MS")

        z0 = float(sub["prof_bin"].min())
        z1 = float(sub["prof_bin"].max())
        full_z = np.arange(np.floor(z0), np.ceil(z1) + 1.0, 1.0, dtype=float)

        # Agregar por celda y pivotar
        g = sub.groupby(["prof_bin", "fecha"], as_index=False)[col_temp].mean()
        piv = g.pivot(index="prof_bin", columns="fecha", values=col_temp)
        piv = piv.reindex(index=full_z, columns=full_t)

        # Interpolación 2D suave:
        # 1) vertical (en profundidad)
        piv = piv.interpolate(method="linear", axis=0, limit_area="inside")
        # 2) temporal (en meses) — usamos 'time' sobre DatetimeIndex (transponemos)
        piv = piv.T.interpolate(method="time", limit_area="inside").T

        return piv

    def _build_station_grid_annual(est: int) -> pd.DataFrame:
        sub = work[work[col_estacion] == est]
        pivot = sub.pivot(index="prof_bin", columns=col_anio, values=col_temp)
        return pivot.sort_index().sort_index(axis=1)

    if stations == [1, 2, 3]:
        fig = make_subplots(
            rows=1,
            cols=3,
            subplot_titles=("Estación 1", "Estación 2", "Estación 3"),
            shared_yaxes=True,
            horizontal_spacing=0.03,
        )
        for idx, est in enumerate([1, 2, 3], start=1):
            is_annual = resolucion == "Media Anual (Tendencia)"
            pivot = _build_station_grid_annual(est) if is_annual else _build_station_grid_monthly(est)
            if pivot.empty:
                continue
            # Heatmap (más estable que contour para malla mensual)
            fig.add_trace(
                go.Heatmap(
                    x=pivot.columns.to_numpy(),
                    y=pivot.index.to_numpy(dtype=float),
                    z=pivot.values,
                    colorscale="RdBu_r",
                    connectgaps=True,
                    showscale=(idx == 3),
                    colorbar=dict(title="Temp (ºC)") if idx == 3 else None,
                    hovertemplate=(
                        "Año: %{x:.0f}<br>Profundidad: %{y:.0f} m<br>Temperatura: %{z:.2f} ºC<extra></extra>"
                        if is_annual
                        else "Fecha: %{x|%b %Y}<br>Profundidad: %{y:.0f} m<br>Temperatura: %{z:.2f} ºC<extra></extra>"
                    ),
                ),
                row=1,
                col=idx,
            )
            if is_annual:
                fig.update_xaxes(title_text="Año", tickformat="d", dtick=1, row=1, col=idx)
            else:
                fig.update_xaxes(title_text="Fecha", row=1, col=idx)
        fig.update_yaxes(title_text="Profundidad (m)", autorange="reversed", row=1, col=1)
        fig.update_layout(
            template="simple_white",
            title="Evolución termoclina (Hovmöller) — Comparativa",
            height=560,
            margin=dict(t=70),
        )
        return fig

    est = stations[0]
    is_annual = resolucion == "Media Anual (Tendencia)"
    pivot = _build_station_grid_annual(est) if is_annual else _build_station_grid_monthly(est)
    fig = go.Figure()
    if not pivot.empty:
        fig.add_trace(
            go.Heatmap(
                x=pivot.columns.to_numpy(),
                y=pivot.index.to_numpy(dtype=float),
                z=pivot.values,
                colorscale="RdBu_r",
                colorbar=dict(title="Temp (ºC)"),
                connectgaps=True,
                hovertemplate=(
                    "Año: %{x:.0f}<br>Profundidad: %{y:.0f} m<br>Temperatura: %{z:.2f} ºC<extra></extra>"
                    if is_annual
                    else "Fecha: %{x|%b %Y}<br>Profundidad: %{y:.0f} m<br>Temperatura: %{z:.2f} ºC<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        template="simple_white",
        title=f"Evolución termoclina (Hovmöller) — Estación {est}",
        xaxis=(dict(title="Año", tickformat="d", dtick=1) if is_annual else dict(title="Fecha")),
        yaxis=dict(title="Profundidad (m)", autorange="reversed"),
        height=500,
    )
    return fig


if __name__ == "__main__":

    # Bloque de prueba local: leer CSV de Sireno si existe, si no generar dummy.
    df_test = _load_local_csv_if_available()
    if df_test is None:
        print(
            "No se encontró CSV de Sireno en 'data/processed'. "
            "Usando datos sintéticos dummy para prueba local."
        )
        df_test = _generate_dummy_data()

    fig_anual = plot_temp_media_anual(df_test)
    fig_estacional = plot_temp_estacionalidad(df_test)

    # Exportación a HTML interactivo en lugar de abrir ventanas del sistema
    project_root = Path(__file__).resolve().parents[1]
    figures_dir = project_root / "outputs" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    path_anual = figures_dir / "temp_media_anual_sireno.html"
    path_estacional = figures_dir / "temp_estacionalidad_sireno.html"

    fig_anual.write_html(path_anual)
    print(f"Gráfico de tendencia interanual guardado en: {path_anual}")

    fig_estacional.write_html(path_estacional)
    print(f"Gráfico de estacionalidad guardado en: {path_estacional}")


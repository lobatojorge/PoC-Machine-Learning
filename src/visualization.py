"""
src/visualization.py
====================
Fachada (Facade Pattern) sobre ``src/03_visualization.py``.

``03_visualization.py`` sigue la convención de numeración del pipeline
(00_, 01_, … 03_) que es valiosa como documentación del orden de ejecución,
pero el prefijo numérico impide importarlo con ``import`` estándar de Python.

Este módulo resuelve el problema de una sola vez:
  - Carga el archivo mediante ``importlib`` (único punto donde se hace).
  - Re-exporta cada función pública con un nombre resoluble por cualquier
    IDE / type-checker.
  - ``app.py`` y cualquier otro cliente importan desde aquí; nunca tienen
    que conocer la mecánica interna.

Funciones expuestas
-------------------
- plot_temp_5m_anual: temperatura media anual a ~5 m por estación (1, 2, 3).
- plot_hovmoller: mapa de calor profundidad × tiempo.
- plot_wginor_anomaly / plot_wginor_dual_anomaly: anomalías anuales WGINOR.

Uso
---
    from src.visualization import plot_temp_5m_anual, plot_hovmoller, ...
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Carga del módulo subyacente — se ejecuta UNA sola vez gracias a sys.modules
# ---------------------------------------------------------------------------
_VIZ_MODULE_NAME = "_ieo_viz03"
_VIZ_PATH = Path(__file__).with_name("03_visualization.py")

if _VIZ_MODULE_NAME not in sys.modules:
    if not _VIZ_PATH.exists():
        raise ImportError(
            f"No se encontró el módulo de visualización en: {_VIZ_PATH}\n"
            "Asegúrate de que 'src/03_visualization.py' existe en el proyecto."
        )
    _spec = importlib.util.spec_from_file_location(_VIZ_MODULE_NAME, _VIZ_PATH)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"No se pudo crear el spec para {_VIZ_PATH}")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    sys.modules[_VIZ_MODULE_NAME] = _mod

_viz = sys.modules[_VIZ_MODULE_NAME]

# ---------------------------------------------------------------------------
# Re-exportación pública — nombres válidos, tipados como Callable
# ---------------------------------------------------------------------------

def plot_wginor_anomaly(
    df: pd.DataFrame,
    col_anio: str,
    col_var: str,
    titulo: str,
    color_pos: str,
    color_neg: str,
    ylabel: str,
) -> go.Figure:
    """Anomalías anuales WGINOR para una variable. Delega en 03_visualization."""
    return _viz.plot_wginor_anomaly(  # type: ignore[no-any-return]
        df,
        col_anio=col_anio,
        col_var=col_var,
        titulo=titulo,
        color_pos=color_pos,
        color_neg=color_neg,
        ylabel=ylabel,
    )


def plot_wginor_dual_anomaly(
    df: pd.DataFrame,
    col_anio: str,
    col_temp: str,
    col_sal: str,
    label_temp: str = "Temperatura",
    label_sal: str = "Salinidad",
    titulo: str = "Anomalías Anuales de Temperatura y Salinidad",
) -> go.Figure:
    """Anomalías anuales de doble eje WGINOR. Delega en 03_visualization."""
    return _viz.plot_wginor_dual_anomaly(  # type: ignore[no-any-return]
        df,
        col_anio=col_anio,
        col_temp=col_temp,
        col_sal=col_sal,
        label_temp=label_temp,
        label_sal=label_sal,
        titulo=titulo,
    )


def plot_hovmoller(
    df: pd.DataFrame,
    col_anio: str,
    col_profundidad: str,
    col_var: str,
    titulo: str,
    colorscale: str,
    thermocline_depth: Optional[float] = None,
) -> go.Figure:
    """Diagrama de Hovmöller profundidad × año. Delega en 03_visualization."""
    return _viz.plot_hovmoller(  # type: ignore[no-any-return]
        df,
        col_anio=col_anio,
        col_profundidad=col_profundidad,
        col_var=col_var,
        titulo=titulo,
        colorscale=colorscale,
        thermocline_depth=thermocline_depth,
    )


def plot_evolucion_temperatura_termoclina(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: Optional[str] = None,
) -> Tuple[go.Figure, Optional[float]]:
    """Temperatura en la profundidad de la termoclina. Delega en 03_visualization."""
    return _viz.plot_evolucion_temperatura_termoclina(  # type: ignore[no-any-return]
        df,
        col_anio=col_anio,
        col_prof=col_prof,
        col_temp=col_temp,
        col_estacion=col_estacion,
    )


def plot_temp_media_anual(df: pd.DataFrame) -> go.Figure:
    """Temperatura media anual interanual. Delega en 03_visualization."""
    return _viz.plot_temp_media_anual(df)  # type: ignore[no-any-return]


def plot_temp_estacionalidad(df: pd.DataFrame) -> go.Figure:
    """Estacionalidad intraanual. Delega en 03_visualization."""
    return _viz.plot_temp_estacionalidad(df)  # type: ignore[no-any-return]


def plot_wginor_temperature_anomaly(
    df: pd.DataFrame,
    col_anio: str = "año",
    col_temp: str = "temperatura",
) -> go.Figure:
    """Anomalía térmica estilo WGINOR. Delega en 03_visualization."""
    return _viz.plot_wginor_temperature_anomaly(  # type: ignore[no-any-return]
        df, col_anio=col_anio, col_temp=col_temp
    )


def plot_perfil_vertical(df: pd.DataFrame) -> go.Figure:
    """Perfil vertical CTD (temperatura + salinidad). Delega en 03_visualization."""
    return _viz.plot_perfil_vertical(df)  # type: ignore[no-any-return]


def plot_temp_5m_anual(
    df: pd.DataFrame,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    output_dir: Optional[Path] = None,
) -> go.Figure:
    """Temperatura media anual a ~5 m por estación (1,2,3). Delega en 03_visualization."""
    return _viz.plot_temp_5m_anual(  # type: ignore[no-any-return]
        df,
        col_anio=col_anio,
        col_prof=col_prof,
        col_temp=col_temp,
        col_estacion=col_estacion,
        output_dir=output_dir,
    )


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
    """T(5m) anual por estación + IC95 global (pool total). Delega en 03_visualization."""
    return _viz.plot_temp_5m_anual_estaciones_con_ic_global(  # type: ignore[no-any-return]
        df,
        col_anio=col_anio,
        col_prof=col_prof,
        col_temp=col_temp,
        col_estacion=col_estacion,
        estaciones_visibles=estaciones_visibles,
        nivel_profundidad=nivel_profundidad,
        mostrar_valor_termoclina=mostrar_valor_termoclina,
        forecast_years=forecast_years,
        forecast_degree=forecast_degree,
        forecast_bootstrap=forecast_bootstrap,
        forecast_show_ci=forecast_show_ci,
    )


def plot_hovmoller_termoclina(
    df: pd.DataFrame,
    estado_slider: str,
    col_anio: str,
    col_prof: str,
    col_temp: str,
    col_estacion: str,
    resolucion: str = "Media Mensual (Estacionalidad)",
) -> go.Figure:
    """Hovmöller termoclina por estado del slider. Delega en 03_visualization."""
    return _viz.plot_hovmoller_termoclina(  # type: ignore[no-any-return]
        df,
        estado_slider=estado_slider,
        col_anio=col_anio,
        col_prof=col_prof,
        col_temp=col_temp,
        col_estacion=col_estacion,
        resolucion=resolucion,
    )

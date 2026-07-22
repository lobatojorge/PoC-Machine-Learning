"""Segmentar series temporales para Plotly: líneas solo entre meses consecutivos."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import plotly.graph_objects as go


def split_dates_values_at_month_gaps(
    fechas: pd.Series,
    valores: pd.Series,
    *,
    max_gap_months: int = 1,
) -> list[tuple[list[datetime], list[float]]]:
    """
    Divide (fecha, valor) en tramos donde el salto entre puntos es <= ``max_gap_months`` meses.

    Por defecto ``max_gap_months=1``: solo se unen meses consecutivos en calendario.
    """
    df = pd.DataFrame({"fecha": pd.to_datetime(fechas, errors="coerce"), "y": pd.to_numeric(valores, errors="coerce")})
    df = df.dropna(subset=["fecha", "y"]).sort_values("fecha")
    if df.empty:
        return []

    periods = df["fecha"].dt.to_period("M")
    segments: list[tuple[list[datetime], list[float]]] = []
    x_seg: list[datetime] = []
    y_seg: list[float] = []

    prev_p = periods.iloc[0]
    for i in range(len(df)):
        p = periods.iloc[i]
        if x_seg and int(p.ordinal - prev_p.ordinal) > int(max_gap_months):
            segments.append((x_seg, y_seg))
            x_seg, y_seg = [], []
        x_seg.append(df["fecha"].iloc[i])
        y_seg.append(float(df["y"].iloc[i]))
        prev_p = p

    if x_seg:
        segments.append((x_seg, y_seg))
    return segments


def add_line_markers_by_segments(
    fig: go.Figure,
    fechas: pd.Series,
    valores: pd.Series,
    *,
    max_gap_months: int = 1,
    name: str = "",
    line: dict | None = None,
    marker: dict | None = None,
    legendgroup: str | None = None,
    showlegend: bool = True,
    hovertemplate: str | None = None,
    **scatter_kwargs: Any,
) -> None:
    """Añade uno o varios ``go.Scatter`` (línea+marcador) sin cruzar huecos temporales."""
    segments = split_dates_values_at_month_gaps(fechas, valores, max_gap_months=max_gap_months)
    for i, (xs, ys) in enumerate(segments):
        if not xs:
            continue
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                name=name if i == 0 else name,
                line=line or {},
                marker=marker or {},
                legendgroup=legendgroup,
                showlegend=showlegend and i == 0,
                hovertemplate=hovertemplate,
                **scatter_kwargs,
            )
        )


def add_lines_only_by_segments(
    fig: go.Figure,
    fechas: pd.Series,
    valores: pd.Series,
    *,
    max_gap_months: int = 1,
    name: str = "",
    line: dict | None = None,
    legendgroup: str | None = None,
    showlegend: bool = True,
    hovertemplate: str | None = None,
    **scatter_kwargs: Any,
) -> None:
    """Añade trazos ``lines`` sin marcadores, cortados por huecos."""
    segments = split_dates_values_at_month_gaps(fechas, valores, max_gap_months=max_gap_months)
    for i, (xs, ys) in enumerate(segments):
        if not xs:
            continue
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                name=name,
                line=line or {},
                legendgroup=legendgroup,
                showlegend=showlegend and i == 0,
                hovertemplate=hovertemplate,
                **scatter_kwargs,
            )
        )

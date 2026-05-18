"""Exportación estática (CSV + HTML Plotly) de series temporales mensuales."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go


def write_temporal_temperature_html(
    monthly: pd.DataFrame,
    *,
    out_html: Path,
    title: str,
    subtitle: str,
    y_label: str = "Temperatura (°C)",
    depth_m: float = 5.0,
) -> None:
    """Escribe una figura temporal autocontenida (Plotly vía CDN)."""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    work = monthly.copy()
    work["fecha"] = pd.to_datetime(work["fecha"], errors="coerce")
    work = work.dropna(subset=["fecha", "valor_prof"]).sort_values("fecha")
    if work.empty:
        raise ValueError("Serie mensual vacía; no se puede generar HTML.")

    from ieo.reports.plot_gaps import add_line_markers_by_segments  # noqa: PLC0415

    fig = go.Figure()
    add_line_markers_by_segments(
        fig,
        work["fecha"],
        work["valor_prof"],
        name=f"T a {depth_m:g} m",
        line=dict(color="#00BFFF", width=2),
        marker=dict(size=6),
    )
    fig.update_layout(
        template="plotly_dark",
        title=dict(text=f"{title}<br><sup style='font-size:0.75em'>{subtitle}</sup>", x=0.02),
        xaxis_title="Mes",
        yaxis_title=y_label,
        height=520,
        margin=dict(t=80, b=60),
        hovermode="x unified",
    )
    fig.write_html(str(out_html), include_plotlyjs="cdn", full_html=True)


def station_code_for_radial(radial_id: str, station_sbe: int) -> str | None:
    """
    Mapea ``** Station: N`` (SBE) → código IEO (p. ej. E2SA = estación 2 Santander).

    Primero busca ``E{n}`` en el acrónimo del catálogo; si no, usa posición 1…n (Cudillero E1CU…).
    """
    import re

    from ieo.radiales_catalog import RADIAL_STATION_CODES

    n = int(station_sbe)
    codes = RADIAL_STATION_CODES.get(radial_id, ())
    pat = re.compile(rf"^E{n}[A-Z]", re.IGNORECASE)
    for code in codes:
        if pat.match(code.strip()):
            return code.upper()
    idx = n - 1
    if 0 <= idx < len(codes):
        return codes[idx].upper()
    return None


def build_export_meta(
    stats: dict[str, Any],
    *,
    radial_label: str,
    station_sbe: int,
    station_code: str | None,
    depth_m: float,
    diag: dict[str, float | int],
    n_monthly: int,
) -> dict[str, Any]:
    return {
        "radial": radial_label,
        "station_sbe": station_sbe,
        "station_code_ieo": station_code,
        "depth_m": depth_m,
        "ingesta": stats,
        "mensual": diag,
        "n_puntos_mensuales": n_monthly,
    }

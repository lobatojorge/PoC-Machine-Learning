"""
Funciones de figuras Plotly reutilizables para las radiales Cudillero.

Este módulo no importa Streamlit: puede usarse desde scripts, notebooks
o cualquier otro framework sin necesitar el entorno de Streamlit instalado.

Funciones expuestas
-------------------
- parse_radial_station_coords_from_methodology: extrae lat/lon WGS84 del
  Markdown de metodología (comentario HTML o formato DMS en viñetas).
- build_cudillero_radial_map_figure: mapa interactivo Plotly con las
  estaciones de la radial y la línea del transecto.

Uso desde Streamlit
-------------------
    from ieo.reports.figures_radiales import (
        parse_radial_station_coords_from_methodology,
        build_cudillero_radial_map_figure,
    )

Uso desde un script independiente
----------------------------------
    from pathlib import Path
    from ieo.reports.figures_radiales import (
        parse_radial_station_coords_from_methodology,
        build_cudillero_radial_map_figure,
    )
    md = Path("docs/metodologia_radiales_cudillero.md").read_text()
    stations = parse_radial_station_coords_from_methodology(md)
    fig = build_cudillero_radial_map_figure(stations)
    fig.write_html("mapa_radial.html")
"""

from __future__ import annotations

import re

import numpy as np
import plotly.graph_objects as go


def parse_radial_station_coords_from_methodology(
    md_text: str,
) -> list[dict[str, float | int | str]]:
    """
    Extrae coordenadas lat/lon WGS84 del Markdown de metodología.

    Formatos reconocidos (en orden de precedencia):
    1. Comentario HTML ``<!-- E1 lat lon | E2 lat lon | E3 lat lon | E4 lat lon -->``
    2. Comentario HTML con 3 estaciones.
    3. Viñetas con coordenadas DMS: ``**Estación N · nombre** (DD°MM.m' N, DD°MM.m' W)``.

    Devuelve lista vacía si el texto es el placeholder de metodología pendiente.
    """
    if "<p>Texto de metodología pendiente" in md_text:
        return []

    block4 = re.search(
        r"<!--\s*E1\s+([\d.]+)\s+([-\d.]+)\s*\|\s*E2\s+([\d.]+)\s+([-\d.]+)"
        r"\s*\|\s*E3\s+([\d.]+)\s+([-\d.]+)\s*\|\s*E4\s+([\d.]+)\s+([-\d.]+)\s*-->",
        md_text,
    )
    if block4:
        return [
            {"estacion": 1, "lat": float(block4.group(1)), "lon": float(block4.group(2)), "nombre": "E1 · Costa"},
            {"estacion": 2, "lat": float(block4.group(3)), "lon": float(block4.group(4)), "nombre": "E2 · Plataforma"},
            {"estacion": 3, "lat": float(block4.group(5)), "lon": float(block4.group(6)), "nombre": "E3 · Talud"},
            {"estacion": 4, "lat": float(block4.group(7)), "lon": float(block4.group(8)), "nombre": "E4 · Talud profundo"},
        ]

    block3 = re.search(
        r"<!--\s*E1\s+([\d.]+)\s+([-\d.]+)\s*\|\s*E2\s+([\d.]+)\s+([-\d.]+)"
        r"\s*\|\s*E3\s+([\d.]+)\s+([-\d.]+)\s*-->",
        md_text,
    )
    if block3:
        return [
            {"estacion": 1, "lat": float(block3.group(1)), "lon": float(block3.group(2)), "nombre": "E1CU"},
            {"estacion": 2, "lat": float(block3.group(3)), "lon": float(block3.group(4)), "nombre": "E2CU"},
            {"estacion": 3, "lat": float(block3.group(5)), "lon": float(block3.group(6)), "nombre": "E3CU"},
        ]

    dms_pat = re.compile(
        r"\*\*Estación\s+(\d+)\s*·\s*([^*]+)\*\*\s*\(\s*(\d+)°\s*([\d.]+)\s*['′´]\s*N"
        r"\s*,\s*(\d+)°\s*([\d.]+)\s*['′´]\s*W",
        re.IGNORECASE,
    )
    found: list[dict[str, float | int | str]] = []
    for m in dms_pat.finditer(md_text):
        n = int(m.group(1))
        label = f"E{n} · {m.group(2).strip()}"
        lat_deg, lat_min = int(m.group(3)), float(m.group(4))
        lon_deg, lon_min = int(m.group(5)), float(m.group(6))
        lat = lat_deg + lat_min / 60.0
        lon = -(lon_deg + lon_min / 60.0)
        found.append({"estacion": n, "lat": lat, "lon": lon, "nombre": label})
    found.sort(key=lambda x: int(x["estacion"]))  # type: ignore[arg-type, return-value]
    return found


def build_cantabrico_radials_overview_map(
    cities: list[dict[str, float | int | str]],
    *,
    selected_radial_id: str | None = None,
    interactive_radial_id: str | None = None,
) -> go.Figure:
    """
    Mapa del Cantábrico con una marca por radial (posición media de los ``.cnv``).

    ``customdata`` lleva ``radial_id`` para selección en Streamlit.
    Si ``interactive_radial_id`` está definido, solo esa radial es seleccionable;
    el resto se muestra atenuado (referencia geográfica).
    """
    center_lat, center_lon, zoom = 43.45, -5.35, 6.8
    if cities:
        lats = [float(c["lat"]) for c in cities]
        lons = [float(c["lon"]) for c in cities]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

    fig = go.Figure()
    if cities:
        active = [c for c in cities if not interactive_radial_id or c["radial_id"] == interactive_radial_id]
        muted = [c for c in cities if interactive_radial_id and c["radial_id"] != interactive_radial_id]

        def _add_city_trace(group: list[dict], *, muted_style: bool) -> None:
            if not group:
                return
            lats = [float(c["lat"]) for c in group]
            lons = [float(c["lon"]) for c in group]
            labels = [str(c["label"]) for c in group]
            rids = [str(c["radial_id"]) for c in group]
            counts = [int(c.get("n_cnv", 0)) for c in group]
            sizes = [22 + min(n, 400) // 30 for n in counts] if muted_style else [28 + min(n, 400) // 25 for n in counts]
            if muted_style:
                colors = ["#94a3b8"] * len(group)
                text_colors = ["#94a3b8"] * len(group)
                hover = [
                    f"<b>{lbl}</b><br>Referencia (demo activa en otra localidad)"
                    for lbl in labels
                ]
                custom = np.array([[""] for _ in group])
            else:
                colors = ["#00BFFF" if rid == selected_radial_id else "#2b6cb0" for rid in rids]
                text_colors = ["#1e3a5f"] * len(group)
                hover = [f"<b>{lbl}</b><br>{n:,} perfiles .cnv con coordenadas" for lbl, n in zip(labels, counts)]
                custom = np.array(rids).reshape(-1, 1)
            fig.add_trace(
                go.Scattermap(
                    lat=lats,
                    lon=lons,
                    mode="markers+text",
                    text=labels,
                    textposition="top center",
                    textfont=dict(size=10 if muted_style else 11, color=text_colors[0], family="Arial, sans-serif"),
                    marker=dict(size=sizes, color=colors, opacity=0.45 if muted_style else 0.92),
                    customdata=custom,
                    hovertext=hover,
                    hovertemplate="%{hovertext}<extra></extra>",
                    showlegend=False,
                )
            )

        _add_city_trace(muted, muted_style=True)
        _add_city_trace(active, muted_style=False)

    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=420,
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#f8fafc",
        showlegend=False,
        uirevision="cantabrico_overview",
    )
    return fig


def build_radial_transect_map_figure(
    stations: list[dict[str, float | int | str]],
    *,
    uirevision: str = "radial_transect",
) -> go.Figure:
    """Mapa de estaciones de una radial (transecto + marcadores numerados)."""
    center_lat, center_lon = 43.689, -6.150
    zoom = 8.6
    if stations:
        lats = [float(s["lat"]) for s in stations]
        lons = [float(s["lon"]) for s in stations]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        lat_span = max(lats) - min(lats)
        lon_span = max(lons) - min(lons)
        span = max(lat_span * 1.35, lon_span * 1.6, 0.06)
        zoom = float(np.clip(11.2 - span * 18.0, 7.5, 10.8))

    fig = go.Figure()

    if len(stations) >= 2:
        ordered = sorted(stations, key=lambda s: float(s["lat"]))
        fig.add_trace(
            go.Scattermap(
                lat=[float(s["lat"]) for s in ordered],
                lon=[float(s["lon"]) for s in ordered],
                mode="lines",
                line=dict(color="rgba(30,58,95,0.4)", width=2),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if stations:
        _DEPTH_COLORS = ["#5ea8d4", "#2b6cb0", "#1a3f6f", "#0c1f3f", "#081828"]
        lats = [float(s["lat"]) for s in stations]
        lons = [float(s["lon"]) for s in stations]
        ids = [int(s["estacion"]) for s in stations]
        colors = [_DEPTH_COLORS[min(i - 1, len(_DEPTH_COLORS) - 1)] for i in ids]
        sizes_mapped = [22 + min(i, 8) for i in ids]
        hover_texts = [f"<b>{s.get('nombre', f'Estación {i}')}</b>" for i, s in zip(ids, stations)]

        fig.add_trace(
            go.Scattermap(
                lat=lats,
                lon=lons,
                mode="markers+text",
                text=[str(i) for i in ids],
                textposition="middle center",
                textfont=dict(size=11, color="#ffffff", family="Arial, sans-serif"),
                marker=dict(size=sizes_mapped, color=colors, symbol="circle", opacity=0.95),
                customdata=np.array(ids).reshape(-1, 1),
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            )
        )

    fig.update_layout(
        map=dict(
            style="carto-positron",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=460,
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#f8fafc",
        showlegend=False,
        uirevision=uirevision,
    )
    return fig


def build_cudillero_radial_map_figure(
    stations: list[dict[str, float | int | str]],
) -> go.Figure:
    """Alias de compatibilidad → :func:`build_radial_transect_map_figure`."""
    return build_radial_transect_map_figure(stations, uirevision="cudillero_map")

# -*- coding: utf-8 -*-
"""Capa de presentacion EWS del visor Streamlit."""

from __future__ import annotations

import streamlit as st

_SVG = (
    "width='20' height='20' viewBox='0 0 24 24' fill='none' "
    "stroke='#00BFFF' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'"
)

# Cada paso: (titulo, icono_svg) o (titulo, subtitulo, icono_svg). Subtitulo vacio = no se muestra.
_ARCH_STEPS: tuple[tuple[str, ...], ...] = (
    (
        "Ingesta",
        "Perfiles CTD en formato .cnv",
        f"<svg {_SVG}><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z'/>"
        f"<path d='M14 2v6h6'/></svg>",
    ),
    (
        "Primera revisión",
        "Lo que no cumple mínimos, apartado y contado",
        f"<svg {_SVG}><path d='m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 22h16a2 2 0 0 0 1.73-4Z'/>"
        f"<line x1='12' y1='9' x2='12' y2='13'/></svg>",
    ),
    (
        "Unificación de formato",
        f"<svg {_SVG}><ellipse cx='12' cy='5' rx='9' ry='3'/><path d='M3 5v14a9 3 0 0 0 18 0V5'/></svg>",
    ),
    (
        "Reglas de calidad",
        "Revisión de rangos",
        f"<svg {_SVG}><path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10'/></svg>",
    ),
    (
        "Detección anomalías",
        "Isolation Forest",
        f"<svg {_SVG}><path d='M22 12h-4l-3 9L9 3l-3 9H2'/></svg>",
    ),
    (
        "Visor",
        f"<svg {_SVG}><rect x='3' y='3' width='18' height='18' rx='2'/><path d='M3 9h18'/></svg>",
    ),
)


def _parse_arch_step(step: tuple[str, ...]) -> tuple[str, str, str]:
    """(titulo, icono) o (titulo, subtitulo, icono)."""
    if len(step) == 2:
        return str(step[0]), str(step[1]), ""
    if len(step) == 3:
        return str(step[0]), str(step[2]), str(step[1]).strip()
    raise ValueError(
        f"Paso de arquitectura invalido (use 2 o 3 elementos): {step!r}"
    )


def inject_presentation_css() -> None:
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.ews-hero {
    background: linear-gradient(135deg, #0E1626 0%, #080D16 55%, #0a1a2e 100%);
    border: 1px solid rgba(0,191,255,0.2);
    border-radius: 14px;
    padding: 22px 28px 18px;
    margin-bottom: 12px;
}
.ews-hero-badge {
    display: inline-flex;
    padding: 4px 12px;
    border-radius: 9999px;
    border: 1px solid rgba(0,191,255,0.35);
    background: rgba(0,191,255,0.1);
    font-family: "JetBrains Mono", monospace;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    color: #00BFFF;
    margin-bottom: 10px;
}
.ews-hero h1 {
    font-family: "Plus Jakarta Sans", sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: #E2EAF4;
    margin: 0 0 8px;
    line-height: 1.15;
}
.ews-hero-foot {
    font-size: 0.88rem;
    color: #A8BBCF;
    margin: 0;
    line-height: 1.5;
    max-width: 920px;
}
.arch-flow {
    display: flex;
    align-items: stretch;
    gap: 0;
    margin-bottom: 16px;
    overflow-x: auto;
}
.arch-step {
    flex: 1;
    min-width: 108px;
    border: 1px solid rgba(255,255,255,0.07);
    border-top: 2px solid #00BFFF;
    border-radius: 8px;
    padding: 10px 12px 8px;
    background: #0E1626;
    text-align: center;
}
.arch-step-icon { line-height: 1; margin-bottom: 6px; }
.arch-step-title {
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #E2EAF4;
    margin-bottom: 2px;
}
.arch-step-sub {
    font-size: 0.58rem;
    font-family: "JetBrains Mono", monospace;
    color: #5B7FA3;
}
.arch-arrow {
    display: flex;
    align-items: center;
    color: #5B7FA3;
    font-size: 1rem;
    padding: 0 2px;
    flex-shrink: 0;
}
.ews-alert-panel {
    border: 1px solid rgba(239,68,68,0.35);
    border-left: 4px solid #ef4444;
    border-radius: 10px;
    background: linear-gradient(90deg, rgba(239,68,68,0.08) 0%, #0E1626 42%);
    padding: 14px 18px;
    margin-bottom: 16px;
}
.ews-alert-panel.warn {
    border-color: rgba(245,158,11,0.35);
    border-left-color: #f59e0b;
    background: linear-gradient(90deg, rgba(245,158,11,0.08) 0%, #0E1626 42%);
}
.ews-alert-line {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #E2EAF4;
    margin: 4px 0;
    padding: 6px 10px;
    border-radius: 6px;
    background: rgba(0,0,0,0.25);
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_ews_hero(*, tagline: str | None = None) -> None:
    foot = tagline or (
        "Plataforma de visualización de perfiles CTD"
    )
    st.markdown(
        f'<div class="ews-hero">'
        f'<span class="ews-hero-badge">Sistema detección temprana</span>'
        f"<h1>PROYECTO RADIALES</h1>"
        f'<p class="ews-hero-foot">{foot}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_architecture_flow() -> None:
    parts: list[str] = []
    for i, raw in enumerate(_ARCH_STEPS):
        title, icon, sub = _parse_arch_step(raw)
        if i:
            parts.append('<div class="arch-arrow" aria-hidden="true">&rsaquo;</div>')
        sub_html = f'<div class="arch-step-sub">{sub}</div>' if sub else ""
        parts.append(
            f'<div class="arch-step">'
            f'<div class="arch-step-icon">{icon}</div>'
            f'<div class="arch-step-title">{title}</div>'
            f"{sub_html}"
            f"</div>"
        )
    st.markdown(
        '<p style="font-size:0.65rem;font-family:&quot;JetBrains Mono&quot;,monospace;'
        'font-weight:700;text-transform:uppercase;letter-spacing:0.18em;color:#00BFFF;'
        'margin:0 0 6px;"></p>'
        '<p style="font-size:0.8rem;color:#A8BBCF;margin:0 0 10px;line-height:1.45;max-width:920px;">'
        "El visor es la última capa de un sistema que audita e identifica anomalías en los datos:"
        f'<div class="arch-flow">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def render_alert_stream(*, extra_lines: list[tuple[str, str]] | None = None) -> None:
    """Panel de alertas puntuales (p. ej. contrato bajo una grafica)."""
    lines = list(extra_lines or [])
    if not lines:
        return
    
    has_error = any(s == "error" for s, _ in lines)
    panel_class = "" if has_error else "warn"
    panel_title = "Errores del Contrato de Datos" if has_error else "Avisos del Contrato de Datos"
    
    body = "".join(
        f"<div style='display:flex;align-items:flex-start;gap:8px;padding:8px 0;"
        f"border-bottom:1px solid rgba(255,255,255,0.05);line-height:1.4;'>"
        f"<span style='font-size:0.76rem;color:#E2EAF4;'>{msg}</span>"
        f"</div>"
        for s, msg in lines[:10]
    )
    st.markdown(
        f"<div class='ews-alert-panel {panel_class}'>"
        f"<p style='font-size:0.75rem;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.12em;color:#E2EAF4;margin:0 0 8px;'>"
        f"{panel_title}</p>"
        f"{body}"
        f"</div>",
        unsafe_allow_html=True,
    )

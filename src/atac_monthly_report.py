from __future__ import annotations

"""
src/atac_monthly_report.py
==========================

Figura única (mensual) inspirada en ATAC (visualización), usando:
- Ajuste base tipo Marcos: tendencia lineal + estacionalidad mensual fija.
- Bandas de incertidumbre: residuos Marcos iid gaussianos (σ constante, sin AR).
- Holdout: últimos 12 meses excluidos del ajuste; bandas 50/75/95 % en validación.
- Líneas solo entre meses consecutivos (sin unir campañas separadas).

Este módulo devuelve:
- Una figura Plotly con leyenda ordenada y agrupada.
- Un texto corto (Markdown) “al pie” explicando qué se ve y cómo interpretarlo.
"""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go


@dataclass(frozen=True, slots=True)
class AtacMonthlyResult:
    fig: go.Figure
    footer_md: str
    pipe: pd.DataFrame
    meta: dict[str, Any]
    gap_summary: str  # frase compacta de huecos (vacía si no hay ninguno significativo)


def _load_analysis_module(project_root: Path) -> Any:
    key = "ieo_02_analysis"
    if key in sys.modules:
        return sys.modules[key]
    path = project_root / "src" / "02_analysis.py"
    spec = importlib.util.spec_from_file_location(key, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar el módulo de análisis: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[key] = mod
    return mod


def _describe_long_month_gaps(
    dates: pd.Series, *, min_gap_months: int = 3
) -> tuple[list[str], str]:
    """Entre dos meses con observación, detecta huecos ≥ min_gap_months.

    Returns
    -------
    lines : list of detailed markdown strings (one per gap)
    summary : single human sentence summarising all gaps (empty string if none)
    """
    s = pd.to_datetime(dates, errors="coerce").dropna().sort_values()
    if s.empty or len(s) < 2:
        return [], ""
    periods = sorted({p for p in s.dt.to_period("M")})
    gaps: list[tuple[int, str, str]] = []
    lines: list[str] = []
    for a_per, b_per in zip(periods[:-1], periods[1:]):
        gap = int(b_per.ordinal - a_per.ordinal - 1)
        if gap >= min_gap_months:
            a_ts = a_per.to_timestamp(how="start")
            b_ts = b_per.to_timestamp(how="start")
            a_str = a_ts.strftime("%b %Y")
            b_str = b_ts.strftime("%b %Y")
            gaps.append((gap, a_str, b_str))
            lines.append(f"- {a_str} → {b_str}: {gap} meses sin observación.")
    if not gaps:
        return [], ""
    n = len(gaps)
    biggest = max(gaps, key=lambda x: x[0])
    if n == 1:
        summary = f"Sin datos entre {biggest[1]} y {biggest[2]} ({biggest[0]} meses)."
    else:
        summary = (
            f"{n} períodos sin campaña; el mayor entre {biggest[1]} y {biggest[2]} "
            f"({biggest[0]} meses)."
        )
    return lines, summary


def build_atac_monthly_figure(
    *,
    project_root: Path,
    monthly_5m: pd.DataFrame,
    station_label: str,
    holdout_months: int = 12,
    var_label: str = "Temperatura",
    var_units: str = "°C",
    depth_m: int = 5,
) -> AtacMonthlyResult:
    """
    monthly_5m: DataFrame con columnas:
      - fecha (datetime mensual)
      - temp_5m (valor mensual de la variable, nombre fijo internamente)
      - opcional: obs_lower, obs_upper (IC95 de muestreo si n>=2)

    var_label : nombre legible de la variable (p. ej. "Fluorescencia", "PAR", "Oxígeno").
    var_units : unidades para ejes y tooltips (p. ej. "μg/L", "μE/m²/s", "mL/L").
    """
    analysis = _load_analysis_module(project_root)
    holdout_months = int(max(1, holdout_months))

    base = monthly_5m.copy()
    if isinstance(base.columns, pd.MultiIndex):
        base.columns = [
            str(tup[-1]) if isinstance(tup, tuple) and len(tup) > 0 and str(tup[-1]) else str(tup[0])
            for tup in base.columns
        ]
    if "fecha" not in base.columns:
        for c in list(base.columns):
            if pd.api.types.is_datetime64_any_dtype(base[c]) or str(c).lower().strip() == "fecha":
                base = base.rename(columns={c: "fecha"})
                break
    if "fecha" not in base.columns:
        raise KeyError(
            "fecha: el DataFrame mensual debe incluir una columna de fecha (p. ej. 'fecha'). "
            f"Columnas recibidas: {list(base.columns)}"
        )
    if "temp_5m" not in base.columns:
        for c in list(base.columns):
            if c == "fecha":
                continue
            if pd.api.types.is_numeric_dtype(base[c]):
                base = base.rename(columns={c: "temp_5m"})
                break
    if "temp_5m" not in base.columns:
        raise KeyError(
            "temp_5m: el DataFrame mensual debe incluir la temperatura a 5 m. "
            f"Columnas recibidas: {list(base.columns)}"
        )

    base["fecha"] = pd.to_datetime(base["fecha"], errors="coerce")
    base["temp_5m"] = pd.to_numeric(base["temp_5m"], errors="coerce")
    base = base.dropna(subset=["fecha"]).sort_values("fecha")
    from ieo.validation.radial_contract import filter_sampling_dates_pandas  # noqa: PLC0415

    base, _ = filter_sampling_dates_pandas(base, col_fecha="fecha")
    if base.empty:
        raise ValueError("Serie mensual vacía tras filtrar fechas fuera de rango operativo.")

    gap_lines, gap_summary = _describe_long_month_gaps(base["fecha"], min_gap_months=3)

    dec, meta_m = analysis.decompose_marcos_holdout_last_n(
        base,
        col_fecha="fecha",
        col_y="temp_5m",
        holdout_months=holdout_months,
    )
    if dec.empty:
        raise ValueError(f"No se pudo ajustar el modelo base (Marcos): {meta_m}")

    holdout_eff = int(float(meta_m.get("holdout_months", holdout_months)))
    cutoff = pd.to_datetime(meta_m["cutoff_holdout_start"])

    rs = dec.loc[dec["fecha"] < cutoff].set_index("fecha")["residual"]
    atac_df, meta_a = analysis.atac_holdout_bands_on_residuals(
        rs,
        cutoff_holdout_start=cutoff,
        holdout_months=holdout_eff,
        fechas=dec["fecha"],
    )
    if atac_df.empty:
        raise ValueError(f"No se pudo ajustar ATAC (residuos): {meta_a}")

    pipe = dec.merge(atac_df, on="fecha", how="left")
    pipe["temp_train_lo_95"] = pipe["fitted"] + pipe["resid_lo_95"].fillna(0.0)
    pipe["temp_train_hi_95"] = pipe["fitted"] + pipe["resid_hi_95"].fillna(0.0)

    pipe["temp_fc_mean"] = pipe["fitted"] + pipe["resid_fc_mean"].fillna(0.0)
    for lab in ("95", "75", "50"):
        lo = f"resid_fc_lo_{lab}"
        hi = f"resid_fc_hi_{lab}"
        if lo in pipe.columns:
            pipe[f"temp_fc_lo_{lab}"] = pipe["fitted"] + pipe[lo].fillna(0.0)
        if hi in pipe.columns:
            pipe[f"temp_fc_hi_{lab}"] = pipe["fitted"] + pipe[hi].fillna(0.0)

    # ---------------- Figura ----------------
    work = pipe.copy().sort_values("fecha")
    ok = work["observation"].notna()
    is_holdout = work["is_holdout"] == True  # noqa: E712
    is_train = work["is_holdout"] == False  # noqa: E712

    y0 = int(work.loc[ok, "fecha"].min().year)
    y1 = int(work.loc[ok, "fecha"].max().year)

    fig = go.Figure()

    # (1) Rango esperable del modelo (95%) — primero en la leyenda
    if "temp_train_lo_95" in work.columns and "temp_train_hi_95" in work.columns:
        width = (work["temp_train_hi_95"] - work["temp_train_lo_95"]).abs()
        good = is_train & width.notna()
        if good.any():
            thr = float(np.nanquantile(width[good].to_numpy(dtype=float), 0.95)) * 3.0
            good = good & (width <= thr)
        fig.add_trace(
            go.Scatter(
                x=work.loc[good, "fecha"],
                y=work.loc[good, "temp_train_hi_95"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
                legendgroup="modelo",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=work.loc[good, "fecha"],
                y=work.loc[good, "temp_train_lo_95"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(16,78,139,0.18)",
                name="Modelo: rango esperable 95%",
                hoverinfo="skip",
                legendgroup="modelo",
                legendgrouptitle_text="Modelo (histórico)",
            )
        )

    from ieo.reports.plot_gaps import add_lines_only_by_segments  # noqa: PLC0415

    obs_df = work.loc[ok]
    ht = f"modelo:(%{{y:.2f}} {var_units})<extra></extra>"

    # (2) Ajuste base (Marcos) — línea discontinua por tramos entre meses consecutivos
    add_lines_only_by_segments(
        fig,
        obs_df["fecha"],
        obs_df["fitted"],
        name="Modelo base (tendencia + ciclo mensual)",
        line=dict(color="#104E8B", width=1.8, dash="dash"),
        legendgroup="modelo",
        hovertemplate=ht,
        hoverlabel=dict(namelength=0),
    )

    # (3) Observación — solo marcadores
    fig.add_trace(
        go.Scatter(
            x=obs_df["fecha"],
            y=obs_df["observation"],
            mode="markers",
            name="Observación",
            marker=dict(color="#104E8B", size=7, symbol="circle-open"),
            legendgroup="obs",
            legendgrouptitle_text="Observación",
            hovertemplate=f"(%{{y:.2f}} {var_units})<extra></extra>",
            hoverlabel=dict(namelength=0),
        )
    )

    # (4) Pronóstico (holdout) — tonos rojizos, apilando porcentajes en leyenda
    red = "#8B1A1A"
    if is_holdout.any():
        wf = work.loc[is_holdout].copy()
        # Orden de leyenda: 95, 75, 50, media
        for lab, alpha_fill in [("95", 0.30), ("75", 0.22), ("50", 0.14)]:
            lo = f"temp_fc_lo_{lab}"
            hi = f"temp_fc_hi_{lab}"
            if lo not in wf.columns or hi not in wf.columns:
                continue
            fig.add_trace(
                go.Scatter(
                    x=wf["fecha"],
                    y=wf[hi],
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="forecast",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=wf["fecha"],
                    y=wf[lo],
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor=f"rgba(139,26,26,{alpha_fill})",
                    name="Bandas (95%, 75%, 50%)" if lab == "95" else f"banda {lab}%",
                    showlegend=(lab == "95"),
                    hoverinfo="skip",
                    legendgroup="forecast",
                    legendgrouptitle_text="Pronóstico" if lab == "95" else None,
                )
            )
        add_lines_only_by_segments(
            fig,
            wf["fecha"],
            wf["temp_fc_mean"],
            name="media",
            line=dict(color=red, width=2.0),
            legendgroup="forecast",
            hovertemplate=f"modelo:(%{{y:.2f}} {var_units})<extra></extra>",
            hoverlabel=dict(namelength=0),
        )
        # Bandas invisibles con un solo mes: reforzar con segmentos verticales
        if len(wf) == 1:
            row = wf.iloc[0]
            fx = row["fecha"]
            for lab, alpha_fill in [("95", 0.30), ("75", 0.22), ("50", 0.14)]:
                lo = f"temp_fc_lo_{lab}"
                hi = f"temp_fc_hi_{lab}"
                if lo not in wf.columns or hi not in wf.columns:
                    continue
                y0, y1 = float(row[lo]), float(row[hi])
                fig.add_trace(
                    go.Scatter(
                        x=[fx, fx],
                        y=[y0, y1],
                        mode="lines",
                        line=dict(width=6, color=f"rgba(139,26,26,{alpha_fill + 0.25})"),
                        showlegend=False,
                        hoverinfo="skip",
                        legendgroup="forecast",
                    )
                )

    cutoff_txt = cutoff.strftime("%Y-%m")
    sigma_txt = meta_a.get("residual_sigma", "n/d")

    fig.update_layout(
        template="simple_white",
        height=400,
        hovermode="x unified",
        title=dict(
            text=f"{var_label} mensual · {station_label} · {depth_m} m",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13, color="#A8BBCF"),
            x=0.0,
            xanchor="left",
            pad=dict(l=6, t=4),
        ),
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=11),
        ),
        margin=dict(t=50, b=40, r=150),
        xaxis=dict(title="", hoverformat="%B %Y"),
        yaxis=dict(title=f"{var_units}"),
    )

    # Pie de figura — 5 preguntas Q&A para el grid del visor.
    # Formato: pares "Q|||A" separados por "\n\n---\n\n"
    gap_answer = (
        f"{gap_summary} La línea del modelo continúa sin interrupción porque el ciclo "
        "estacional es un parámetro matemático, no requiere datos recientes."
        if gap_summary
        else "No hay huecos significativos (≥ 3 meses) en la serie."
    )

    footer_md = "\n\n---\n\n".join([
        f"¿Por qué la línea serpentea?|||"
        f"La curva discontinua incorpora un <b>ciclo estacional mensual</b> ajustado sobre el histórico: "
        f"sube en verano y baja en invierno. Antes, con datos de varias radiales mezcladas, ese patrón quedaba "
        f"enmascarado por la dispersión.",

        f"¿Cómo se agrupan los datos si hay varios lances en un mismo mes?|||"
        f"Si en un mismo mes se realizan varias campañas o lances de CTD, <b>no se calcula la media</b> de los valores. "
        f"En su lugar, el sistema selecciona el lance que ha alcanzado la <b>mayor profundidad máxima (z_max)</b>. "
        f"Esto garantiza la integridad del perfil vertical (los lances menos profundos suelen ser lances abortados o de prueba) "
        f"y evita sesgar o difuminar las masas de agua mezclando campañas de fechas distintas.",

        f"¿Qué es la banda azul?|||"
        f"Muestra el <b>rango esperable</b> del ajuste Marcos (±95 % sobre residuos iid, σ≈{sigma_txt}). "
        f"No hay memoria en el error: la anchura es <b>constante</b>, no crece mes a mes.",

        f"¿Qué es el tramo rojo?|||"
        f"El <b>último mes con observación</b> ({cutoff_txt}) se excluye del ajuste: el pronóstico "
        f"se calcula solo con meses anteriores. "
        f"Si el punto cae dentro de la banda 95%, el valor reciente es coherente con el histórico.",

        f"¿Por qué hay períodos sin puntos?|||"
        f"{gap_answer}",

        f"¿Puedo usar estos valores en un informe?|||"
        f"Este visor es una herramienta de exploración. Los resultados deben contrastarse con "
        f"el <b>informe científico firmado</b> y la auditoría del instrumental de campaña antes "
        f"de su uso en documentos oficiales.",
    ])

    meta = {**meta_m, **meta_a}
    return AtacMonthlyResult(fig=fig, footer_md=footer_md, pipe=pipe, meta=meta, gap_summary=gap_summary)


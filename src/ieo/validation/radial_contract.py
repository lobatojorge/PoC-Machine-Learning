"""
Contrato de datos — Radiales (perfil CTD + serie mensual agregada).

Objetivo
--------
- Comprobaciones **burdas**: rangos físicos plausibles, saltos mensuales imposibles
  (p. ej. >12 °C entre dos meses consecutivos en la misma estación).
- Comprobaciones **finas**: pendiente de la mediana anual (deriva lenta), comparación
  ventanas multi‑anual (posible error de calibración progresivo).

Este módulo es deliberadamente conservador: genera `WARNING` ante patrones raros y
`ERROR` ante valores claramente fuera de rango o saltos extremos. Los umbrales son
configurables vía `RadialContractThresholds`.

Integración
-----------
- Streamlit: antes de dibujar series deben ejecutarse `validate_profile_dataframe` y
  `validate_monthly_radial_series` para variables físicas.
- Pipeline: `validate_canonical_ctd_polars` sobre el Parquet canónico antes de aislar
  “datos limpios” como única fuente de verdad del visor (cuando el flujo lo permita).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

try:
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None  # type: ignore[misc, assignment]


class ViolationSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Violation:
    severity: ViolationSeverity
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RadialContractThresholds:
    """Umbrales por defecto — Cantábrico superficial / plataforma (orden de magnitud)."""

    # Temperatura (°C)
    temp_abs_min: float = -2.0
    temp_abs_max: float = 32.0
    # Salto entre dos meses consecutivos (misma estación, misma serie mensual)
    temp_month_delta_warn_c: float = 6.0
    temp_month_delta_error_c: float = 12.0
    # Gradiente vertical T: dos bandas de Δz (m) tras `temp_adjacent_min_dz_m` (ignora pares demasiado cercanos).
    temp_adjacent_min_dz_m: float = 2.5
    temp_adjacent_band_b_max_m: float = 5.0
    temp_adjacent_max_dz_m: float = 15.0
    temp_adjacent_delta_warn_band_b_c: float = 8.0
    temp_adjacent_delta_error_band_b_c: float = 23.0
    temp_adjacent_delta_warn_band_c_c: float = 10.0
    temp_adjacent_delta_error_band_c_c: float = 24.0
    # Compatibilidad / documentación (banda “fina” histórica ≈ Δz pequeño)
    temp_adjacent_delta_warn_c: float = 5.0
    temp_adjacent_delta_error_c: float = 10.0
    # Deriva: regresión mediana anual vs año (°C / año)
    temp_annual_median_slope_warn_per_year: float = 0.25
    temp_annual_median_slope_error_per_year: float = 0.6
    # Comparación ventanas: últimos N años vs N anteriores (mediana anual media)
    drift_window_years: int = 3
    temp_window_mean_diff_warn_c: float = 0.8

    # Salinidad (PSU) — comprobaciones ligeras si kind=salinity
    sal_abs_min: float = 0.0
    sal_abs_max: float = 42.0
    sal_month_delta_warn_psu: float = 2.5
    sal_month_delta_error_psu: float = 5.0


DEFAULT_THRESHOLDS = RadialContractThresholds()


def infer_variable_kind(col_name: str) -> str:
    c = str(col_name).lower()
    if "temp" in c or c in ("temperatura", "temperatura_c"):
        return "temperature"
    if "sal" in c or "salin" in c:
        return "salinity"
    return "other"


def _violations_sort_key(v: Violation) -> tuple[int, str]:
    sev = 0 if v.severity == ViolationSeverity.ERROR else 1
    return sev, v.code


def _iter_monotonic_depth_segments(
    z: np.ndarray,
    v: np.ndarray,
    *,
    depth_reset_drop_m: float = 1.5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Parte un perfil ordenado por profundidad en segmentos donde z no «resetea» hacia arriba.

    Si varios lances o perfiles se concatenan en el mismo grupo (p. ej. misma fecha gruesa),
    al ordenar por z aparece un salto negativo grande (fondo de un lance → superficie del siguiente).
    El test de gradiente vertical solo debe aplicarse dentro de cada tramo físico (z creciente).
    """
    if len(z) < 2:
        return []
    breaks = np.flatnonzero(np.diff(z) < -float(depth_reset_drop_m)) + 1
    starts = np.concatenate(([0], breaks))
    ends = np.concatenate((breaks, [len(z)]))
    out: list[tuple[np.ndarray, np.ndarray]] = []
    for s, e in zip(starts.tolist(), ends.tolist()):
        if e - s < 2:
            continue
        out.append((z[s:e], v[s:e]))
    return out


def validate_profile_dataframe(
    df: pd.DataFrame,
    *,
    col_prof: str,
    col_value: str,
    col_estacion: str,
    cast_keys: tuple[str, ...] = ("acronimo", "estacion"),
    thresholds: RadialContractThresholds | None = None,
    variable_kind: str | None = None,
) -> list[Violation]:
    """
    Validación por filas de perfiles (antes o después de interpolación).

    - Rangos absolutos (temperatura / salinidad).
    - Por grupo de cast (acronimo+estación si existe): saltos grandes entre niveles
      verticales adyacentes (detector burdo de inversión / datos corruptos). Dentro de
      cada grupo, si la profundidad «resetea» hacia arriba (varios lances concatenados),
      se parte en segmentos monótonos antes de medir el gradiente.
    """
    th = thresholds or DEFAULT_THRESHOLDS
    kind = variable_kind or infer_variable_kind(col_value)
    out: list[Violation] = []

    req = [col_prof, col_value, col_estacion]
    for c in req:
        if c not in df.columns:
            out.append(
                Violation(
                    ViolationSeverity.ERROR,
                    "missing_column",
                    f"Falta columna requerida '{c}' para contrato de perfil.",
                    {"column": c},
                )
            )
            return sorted(out, key=_violations_sort_key)

    select_cols = list(req)
    for k in cast_keys:
        if k in df.columns and k not in select_cols:
            select_cols.append(k)
    work = df[select_cols].copy()
    work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
    work[col_value] = pd.to_numeric(work[col_value], errors="coerce")
    work[col_estacion] = pd.to_numeric(work[col_estacion], errors="coerce")
    work = work.dropna(subset=[col_prof, col_value, col_estacion])

    if work.empty:
        out.append(
            Violation(
                ViolationSeverity.WARNING,
                "empty_after_coerce",
                "No quedan filas numéricas válidas (profundidad/valor/estación).",
            )
        )
        return out

    vals = work[col_value].to_numpy(dtype=float)

    if kind == "temperature":
        bad_lo = vals < th.temp_abs_min
        bad_hi = vals > th.temp_abs_max
        n_bad = int(bad_lo.sum() + bad_hi.sum())
        if n_bad > 0:
            out.append(
                Violation(
                    ViolationSeverity.ERROR,
                    "temp_out_of_absolute_range",
                    f"{n_bad} filas con temperatura fuera de [{th.temp_abs_min}, {th.temp_abs_max}] °C.",
                    {"n_rows": n_bad, "min_seen": float(np.nanmin(vals)), "max_seen": float(np.nanmax(vals))},
                )
            )
    elif kind == "salinity":
        bad_lo = vals < th.sal_abs_min
        bad_hi = vals > th.sal_abs_max
        n_bad = int(bad_lo.sum() + bad_hi.sum())
        if n_bad > 0:
            out.append(
                Violation(
                    ViolationSeverity.ERROR,
                    "salinity_out_of_absolute_range",
                    f"{n_bad} filas con salinidad fuera de [{th.sal_abs_min}, {th.sal_abs_max}] PSU.",
                    {"n_rows": n_bad},
                )
            )

    # Gradientes verticales por cast (misma columna temporal que el perfil si no hay acronimo/cast)
    gcols = [c for c in cast_keys if c in work.columns]
    if not gcols:
        work["_single_profile"] = 1
        gcols = ["_single_profile"]

    n_prof_err = 0
    n_prof_warn = 0
    max_jump_err = 0.0
    max_jump_warn = 0.0

    for _, g in work.groupby(gcols, dropna=False):
        gg = g.sort_values(col_prof)
        z = gg[col_prof].to_numpy(dtype=float)
        v = gg[col_value].to_numpy(dtype=float)
        if len(z) < 2:
            continue
        for zs, vs in _iter_monotonic_depth_segments(z, v):
            dz = np.diff(zs)
            dv = np.diff(vs)
            min_dz = float(th.temp_adjacent_min_dz_m)
            max_dz = float(th.temp_adjacent_max_dz_m)
            b_max = float(th.temp_adjacent_band_b_max_m)
            bands = (
                ((dz >= min_dz) & (dz <= b_max), th.temp_adjacent_delta_error_band_b_c, th.temp_adjacent_delta_warn_band_b_c),
                ((dz > b_max) & (dz <= max_dz), th.temp_adjacent_delta_error_band_c_c, th.temp_adjacent_delta_warn_band_c_c),
            )
            if kind == "temperature":
                seg_err = False
                seg_warn = False
                mx_e = 0.0
                mx_w = 0.0
                for m, e_lim, w_lim in bands:
                    if not np.any(m):
                        continue
                    ad = np.abs(dv[m])
                    if np.any(ad >= float(e_lim)):
                        seg_err = True
                        mx_e = max(mx_e, float(np.max(ad)))
                    elif np.any(ad >= float(w_lim)):
                        seg_warn = True
                        mx_w = max(mx_w, float(np.max(ad)))
                if seg_err:
                    n_prof_err += 1
                    max_jump_err = max(max_jump_err, mx_e)
                elif seg_warn:
                    n_prof_warn += 1
                    max_jump_warn = max(max_jump_warn, mx_w)

    if kind == "temperature":
        if n_prof_err > 0:
            out.append(
                Violation(
                    ViolationSeverity.ERROR,
                    "temp_large_vertical_jump",
                    f"{n_prof_err} perfil(es) con salto vertical T (Δz∈[{th.temp_adjacent_min_dz_m:g},{th.temp_adjacent_band_b_max_m:g}] m "
                    f"≥{th.temp_adjacent_delta_error_band_b_c:g} °C, o Δz∈({th.temp_adjacent_band_b_max_m:g},{th.temp_adjacent_max_dz_m:g}] m "
                    f"≥{th.temp_adjacent_delta_error_band_c_c:g} °C). Máximo observado {max_jump_err:.2f} °C. "
                    "Revisar unidades, mezcla de lances o datos corruptos.",
                    {"n_profiles": n_prof_err, "max_adjacent_delta_c": max_jump_err},
                )
            )
        elif n_prof_warn > 0:
            out.append(
                Violation(
                    ViolationSeverity.WARNING,
                    "temp_moderate_vertical_jump",
                    f"{n_prof_warn} perfil(es) con saltos verticales moderados (máximo {max_jump_warn:.2f} °C). "
                    f"Avisos: Δz∈[{th.temp_adjacent_min_dz_m:g},{th.temp_adjacent_band_b_max_m:g}] m ≥{th.temp_adjacent_delta_warn_band_b_c:g} °C; "
                    f"Δz>{th.temp_adjacent_band_b_max_m:g} m ≥{th.temp_adjacent_delta_warn_band_c_c:g} °C. "
                    "Revisar perfil o unidades.",
                    {"n_profiles": n_prof_warn, "max_adjacent_delta_c": max_jump_warn},
                )
            )

    return sorted(out, key=_violations_sort_key)


def validate_monthly_radial_series(
    monthly: pd.DataFrame,
    *,
    col_fecha: str = "fecha",
    col_val: str = "valor_prof",
    col_estacion: str = "estacion",
    thresholds: RadialContractThresholds | None = None,
    variable_kind: str | None = None,
) -> list[Violation]:
    """
    Serie mensual ya agregada (una fila por estación y mes).

    Incluye saltos mes a mes y deriva interanual suave.
    """
    th = thresholds or DEFAULT_THRESHOLDS
    kind = variable_kind or "temperature"
    out: list[Violation] = []

    need = [col_fecha, col_val, col_estacion]
    for c in need:
        if c not in monthly.columns:
            out.append(
                Violation(
                    ViolationSeverity.ERROR,
                    "missing_column",
                    f"Falta '{c}' en serie mensual.",
                    {"column": c},
                )
            )
            return out

    if kind not in ("temperature", "salinity"):
        return []

    work = monthly.copy()
    work[col_fecha] = pd.to_datetime(work[col_fecha], errors="coerce")
    work[col_val] = pd.to_numeric(work[col_val], errors="coerce")
    work[col_estacion] = pd.to_numeric(work[col_estacion], errors="coerce")
    work = work.dropna(subset=[col_fecha, col_val, col_estacion]).sort_values(col_fecha)

    warm = th.temp_month_delta_warn_c if kind == "temperature" else th.sal_month_delta_warn_psu
    errm = th.temp_month_delta_error_c if kind == "temperature" else th.sal_month_delta_error_psu

    for est in work[col_estacion].dropna().unique():
        sub = work[work[col_estacion] == est].sort_values(col_fecha)
        if len(sub) < 2:
            continue
        v = sub[col_val].to_numpy(dtype=float)
        d = np.abs(np.diff(v))
        max_d = float(np.max(d)) if len(d) else 0.0
        if kind == "temperature":
            if max_d >= errm:
                out.append(
                    Violation(
                        ViolationSeverity.ERROR,
                        "temp_month_to_month_spike",
                        f"Estación {int(est)}: salto máximo entre meses consecutivos "
                        f"{max_d:.2f} °C (umbral error {errm} °C).",
                        {"estacion": int(est), "max_delta_c": max_d},
                    )
                )
            elif max_d >= warm:
                out.append(
                    Violation(
                        ViolationSeverity.WARNING,
                        "temp_month_to_month_jump",
                        f"Estación {int(est)}: salto notable entre meses consecutivos "
                        f"{max_d:.2f} °C (umbral aviso {warm} °C).",
                        {"estacion": int(est), "max_delta_c": max_d},
                    )
                )
        elif kind == "salinity":
            if max_d >= errm:
                out.append(
                    Violation(
                        ViolationSeverity.ERROR,
                        "sal_month_to_month_spike",
                        f"Estación {int(est)}: salto máximo entre meses consecutivos "
                        f"{max_d:.2f} PSU (umbral error {errm}).",
                        {"estacion": int(est), "max_delta_psu": max_d},
                    )
                )
            elif max_d >= warm:
                out.append(
                    Violation(
                        ViolationSeverity.WARNING,
                        "sal_month_to_month_jump",
                        f"Estación {int(est)}: salto notable entre meses consecutivos "
                        f"{max_d:.2f} PSU (umbral aviso {warm}).",
                        {"estacion": int(est), "max_delta_psu": max_d},
                    )
                )

        if kind == "temperature":
            # Deriva: mediana por año (solo temperatura)
            sub_y = sub.copy()
            sub_y["_y"] = sub_y[col_fecha].dt.year
            yearly_med = sub_y.groupby("_y", as_index=True)[col_val].median().sort_index()
            years_arr = yearly_med.index.to_numpy(dtype=int)
            meds_arr = yearly_med.to_numpy(dtype=float)
            if len(years_arr) >= 5:
                slope, _intercept = np.polyfit(years_arr.astype(float), meds_arr, 1)
                slope_f = float(slope)
                lim_w = th.temp_annual_median_slope_warn_per_year
                lim_e = th.temp_annual_median_slope_error_per_year
                if abs(slope_f) >= lim_e:
                    out.append(
                        Violation(
                            ViolationSeverity.ERROR,
                            "temp_annual_median_trend_extreme",
                            f"Estación {int(est)}: pendiente mediana anual ~{slope_f:.3f} °C/año "
                            f"(≥ {lim_e}; revisar calibración o mezcla de fuentes).",
                            {"estacion": int(est), "slope_c_per_year": slope_f},
                        )
                    )
                elif abs(slope_f) >= lim_w:
                    out.append(
                        Violation(
                            ViolationSeverity.WARNING,
                            "temp_annual_median_trend",
                            f"Estación {int(est)}: tendencia fuerte en mediana anual (~{slope_f:.3f} °C/año).",
                            {"estacion": int(est), "slope_c_per_year": slope_f},
                        )
                    )

            if len(years_arr) >= 2 * th.drift_window_years:
                last_y = years_arr[-th.drift_window_years :]
                prev_y = years_arr[-2 * th.drift_window_years : -th.drift_window_years]
                m_last = float(np.nanmedian(meds_arr[-th.drift_window_years :]))
                m_prev = float(np.nanmedian(meds_arr[-2 * th.drift_window_years : -th.drift_window_years]))
                diff = m_last - m_prev
                if abs(diff) >= th.temp_window_mean_diff_warn_c:
                    out.append(
                        Violation(
                            ViolationSeverity.WARNING,
                            "temp_window_median_shift",
                            f"Estación {int(est)}: cambio mediana anual "
                            f"últimos {th.drift_window_years} años vs {th.drift_window_years} anteriores: "
                            f"{diff:+.2f} °C.",
                            {
                                "estacion": int(est),
                                "delta_c": float(diff),
                                "years_last": [int(x) for x in last_y],
                                "years_prev": [int(x) for x in prev_y],
                            },
                        )
                    )

    return sorted(out, key=_violations_sort_key)


def validate_canonical_ctd_polars(
    df: Any,
    *,
    thresholds: RadialContractThresholds | None = None,
) -> list[Violation]:
    """Wrapper sobre Parquet canónico (`fecha`, `estacion`, `profundidad_m`, `temperatura_c`, …)."""
    if pl is None:
        return [
            Violation(
                ViolationSeverity.WARNING,
                "polars_missing",
                "Polars no instalado; salto validación canónica.",
            )
        ]
    if not isinstance(df, pl.DataFrame):
        return [
            Violation(
                ViolationSeverity.ERROR,
                "invalid_input",
                "Se esperaba polars.DataFrame canónico.",
            )
        ]

    pdf = df.to_pandas()
    col_prof = "profundidad_m"
    col_val = "temperatura_c"
    col_fecha = "fecha"
    col_estacion = "estacion"
    if col_prof not in pdf.columns or col_val not in pdf.columns:
        return [
            Violation(
                ViolationSeverity.WARNING,
                "canonical_missing_temp_cols",
                "DataFrame canónico sin profundidad_m/temperatura_c; contrato de temperatura omitido.",
            )
        ]

    if "cast" in pdf.columns:
        ck: tuple[str, ...] = ("cast", col_estacion)
    elif col_fecha in pdf.columns:
        pdf = pdf.copy()
        pdf["_qc_day"] = pd.to_datetime(pdf[col_fecha], errors="coerce").dt.normalize()
        ck = ("_qc_day", col_estacion)
    else:
        ck = (col_estacion,)

    return validate_profile_dataframe(
        pdf,
        col_prof=col_prof,
        col_value=col_val,
        col_estacion=col_estacion,
        cast_keys=ck,
        thresholds=thresholds,
        variable_kind="temperature",
    )


def format_violations_markdown(violations: list[Violation]) -> str:
    lines = []
    for v in violations:
        icon = "🔴" if v.severity == ViolationSeverity.ERROR else "🟠"
        lines.append(f"- {icon} **`{v.code}`** ({v.severity.value}): {v.message}")
    return "\n".join(lines) if lines else "_Sin incidencias._"


def format_contract_warning_postchart(v: Violation) -> str:
    """
    Texto breve para avisos WARNING tras la gráfica (evita interpretarlos como fallo de datos).
    """
    d = v.details or {}
    if v.code == "temp_window_median_shift":
        yl = d.get("years_last") or []
        yp = d.get("years_prev") or []
        delta = d.get("delta_c")
        est = d.get("estacion", "?")
        if yl and yp and delta is not None:
            yi_l = [int(x) for x in yl]
            yi_p = [int(x) for x in yp]

            def _span(years: list[int]) -> str:
                return f"{min(years)}–{max(years)}" if len(years) > 1 else str(years[0])

            diff_f = float(delta)
            sym = "↓" if diff_f < 0 else "↑"
            return (
                f"**Temperatura {_span(yi_l)} vs {_span(yi_p)} (est. {est}):** "
                f"{sym} {abs(diff_f):.2f} °C en la mediana anual del trieno reciente. "
                "*Puede reflejar variabilidad climática, no es un fallo de medición.*"
            )
    if v.code in ("temp_annual_median_trend", "temp_annual_median_trend_extreme"):
        slope = d.get("slope_c_per_year")
        est = d.get("estacion", "?")
        if slope is not None:
            return (
                f"**Tendencia larga (estación {est}):** mediana anual cambia ~**{float(slope):+.3f} °C/año**. "
                "Puede ser real o mezcla de fuentes; no es un fallo automático de datos."
            )
    # Genérico, sin icono emoji (más sobrio en Streamlit)
    return f"**`{v.code}`** · {v.message}"

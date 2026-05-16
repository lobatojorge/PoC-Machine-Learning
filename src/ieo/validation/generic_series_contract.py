"""
Contrato genérico para series temporales numéricas.

Por qué existe este módulo
--------------------------
El contrato radial (`radial_contract.py`) define reglas específicas de
oceanografía costera (umbrales CTD, deriva mediana anual, etc.). Este módulo
implementa la **capa 0**: comprobaciones independientes del dominio que
cualquier serie de sensor puede pasar, ya sean perfiles CTD, series de
temperatura volcánica, datos de calidad de agua o cualquier otra fuente.

Diseño
------
- Mismo tipo de retorno que `radial_contract.py`: ``list[Violation]``.
- Sin acoplamiento a pandas ni a ningún esquema de columnas concreto;
  las funciones reciben arrays o DataFrames y columnas como parámetros.
- Combinable con el contrato de dominio: el visor o el pipeline pueden
  ejecutar primero ``run_generic_contract(...)`` y luego las reglas
  específicas del radial.

Transferibilidad
----------------
Para usar este contrato en un nuevo dominio (volcanes, calidad de agua, etc.):
  1. Llamar a ``run_generic_contract`` con los parámetros del nuevo dominio.
  2. Definir umbrales propios en ``GenericContractThresholds``.
  3. Añadir reglas de dominio específico en un módulo nuevo, reutilizando
     los tipos ``Violation`` y ``ViolationSeverity``.

Ver también
-----------
- ``docs/domain_catalog.md`` — cómo añadir un nuevo dominio al sistema.
- ``docs/arquitectura_validacion_datos.md`` — diagrama de capas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .radial_contract import Violation, ViolationSeverity, _violations_sort_key


# ---------------------------------------------------------------------------
# Configuración de umbrales genéricos
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GenericContractThresholds:
    """
    Umbrales por defecto para el contrato genérico.

    Todos son opcionales; se puede construir una instancia con solo los
    parámetros relevantes para el dominio en cuestión.

    Parámetros
    ----------
    abs_min, abs_max
        Rango físico aceptable. Si son ``None``, el rango no se comprueba.
    max_gap_days
        Brecha máxima entre observaciones consecutivas (en días) antes de
        emitir un WARNING. Si es ``None``, no se comprueba.
    max_trend_per_year
        Pendiente máxima aceptable (unidades de la variable / año) para la
        mediana anual. Si es ``None``, no se comprueba la tendencia.
    warn_trend_per_year
        Umbral de aviso para la pendiente (antes del error).
    min_years_for_trend
        Años mínimos de datos para calcular la tendencia.
    """

    abs_min: float | None = None
    abs_max: float | None = None
    max_gap_days: float | None = None
    warn_trend_per_year: float | None = None
    max_trend_per_year: float | None = None
    min_years_for_trend: int = 5


DEFAULT_GENERIC_THRESHOLDS = GenericContractThresholds()


# ---------------------------------------------------------------------------
# Reglas individuales
# ---------------------------------------------------------------------------


def check_absolute_range(
    values: np.ndarray,
    *,
    abs_min: float | None = None,
    abs_max: float | None = None,
    variable_name: str = "valor",
    units: str = "",
) -> list[Violation]:
    """
    Comprueba que todos los valores están dentro de [abs_min, abs_max].

    Emite ERROR si hay valores fuera de rango.
    Omite la comprobación cuando ``abs_min`` y ``abs_max`` son ``None``.
    """
    out: list[Violation] = []
    vals = np.asarray(values, dtype=float)
    finite = vals[np.isfinite(vals)]
    if len(finite) == 0:
        return out

    n_bad = 0
    if abs_min is not None:
        n_bad += int(np.sum(finite < abs_min))
    if abs_max is not None:
        n_bad += int(np.sum(finite > abs_max))

    if n_bad > 0:
        rng = f"[{abs_min}, {abs_max}]" if abs_min is not None and abs_max is not None else \
              f"≥ {abs_min}" if abs_max is None else f"≤ {abs_max}"
        unit_str = f" {units}" if units else ""
        out.append(
            Violation(
                ViolationSeverity.ERROR,
                "out_of_absolute_range",
                f"{n_bad} observación(es) de '{variable_name}' fuera del rango físico {rng}{unit_str}. "
                "Revisar unidades o fuente de datos.",
                {
                    "variable": variable_name,
                    "n_rows": n_bad,
                    "observed_min": float(np.nanmin(finite)),
                    "observed_max": float(np.nanmax(finite)),
                    "expected_min": abs_min,
                    "expected_max": abs_max,
                },
            )
        )
    return out


def check_duplicate_timestamps(
    df: pd.DataFrame,
    *,
    col_time: str,
    col_id: str | None = None,
    variable_name: str = "serie",
) -> list[Violation]:
    """
    Detecta marcas de tiempo duplicadas, opcionalmente dentro de cada grupo (col_id).

    Emite WARNING: los duplicados no son necesariamente errores (p. ej. varios
    sensores en la misma hora), pero merecen revisión.
    """
    out: list[Violation] = []
    if col_time not in df.columns:
        out.append(
            Violation(
                ViolationSeverity.ERROR,
                "missing_time_column",
                f"Columna de tiempo '{col_time}' no encontrada en '{variable_name}'.",
                {"column": col_time},
            )
        )
        return out

    work = df.copy()
    work[col_time] = pd.to_datetime(work[col_time], errors="coerce")

    if col_id and col_id in df.columns:
        dupes = work.duplicated(subset=[col_time, col_id], keep=False)
    else:
        dupes = work.duplicated(subset=[col_time], keep=False)

    n_dup = int(dupes.sum())
    if n_dup > 0:
        out.append(
            Violation(
                ViolationSeverity.WARNING,
                "duplicate_timestamps",
                f"'{variable_name}': {n_dup} fila(s) con marca de tiempo duplicada"
                + (f" dentro de '{col_id}'" if col_id else "")
                + ". Revisar si son lances distintos o datos repetidos.",
                {"n_rows": n_dup, "variable": variable_name},
            )
        )
    return out


def check_time_gaps(
    df: pd.DataFrame,
    *,
    col_time: str,
    col_id: str | None = None,
    max_gap_days: float,
    variable_name: str = "serie",
) -> list[Violation]:
    """
    Detecta brechas temporales mayores que ``max_gap_days`` días.

    Útil para detectar períodos sin datos que pueden indicar fallo de sensor,
    campaña cancelada o datos no entregados. Emite WARNING.

    Si ``col_id`` está presente, la comprobación se realiza por grupo.
    """
    out: list[Violation] = []
    if col_time not in df.columns:
        return out

    work = df.copy()
    work[col_time] = pd.to_datetime(work[col_time], errors="coerce")
    work = work.dropna(subset=[col_time])

    def _check_group(g: pd.DataFrame, group_label: str) -> None:
        ts = g[col_time].sort_values().reset_index(drop=True)
        if len(ts) < 2:
            return
        gaps = ts.diff().dt.total_seconds() / 86400  # días
        big_gaps = gaps[gaps > max_gap_days].dropna()
        if not big_gaps.empty:
            worst = float(big_gaps.max())
            out.append(
                Violation(
                    ViolationSeverity.WARNING,
                    "time_gap_detected",
                    f"'{variable_name}'{group_label}: brecha de {worst:.1f} días "
                    f"(umbral {max_gap_days} días). Puede indicar campaña faltante o fallo de sensor.",
                    {
                        "variable": variable_name,
                        "max_gap_days": worst,
                        "threshold_days": max_gap_days,
                        "n_gaps": len(big_gaps),
                    },
                )
            )

    if col_id and col_id in df.columns:
        for gid, g in work.groupby(col_id, dropna=False):
            _check_group(g, f" [{col_id}={gid}]")
    else:
        _check_group(work, "")

    return out


def check_extreme_trend(
    df: pd.DataFrame,
    *,
    col_time: str,
    col_value: str,
    col_id: str | None = None,
    warn_trend_per_year: float | None,
    max_trend_per_year: float | None,
    min_years: int = 5,
    variable_name: str = "valor",
    units: str = "",
) -> list[Violation]:
    """
    Ajusta una regresión lineal sobre la mediana anual y avisa si la pendiente
    supera los umbrales.

    Una tendencia extrema puede indicar:
    - Deriva de calibración progresiva (error instrumental).
    - Cambio real documentado (señal climática o volcánica).

    El visor debe mostrar este aviso *con contexto*, no como un fallo absoluto.
    Requiere al menos ``min_years`` años con datos.
    """
    out: list[Violation] = []
    if col_time not in df.columns or col_value not in df.columns:
        return out
    if warn_trend_per_year is None and max_trend_per_year is None:
        return out

    work = df.copy()
    work[col_time] = pd.to_datetime(work[col_time], errors="coerce")
    work[col_value] = pd.to_numeric(work[col_value], errors="coerce")
    work = work.dropna(subset=[col_time, col_value])

    def _check_group(g: pd.DataFrame, group_label: str) -> None:
        g = g.copy()
        g["_year"] = g[col_time].dt.year
        yearly = g.groupby("_year")[col_value].median().sort_index()
        years = yearly.index.to_numpy(dtype=int)
        meds = yearly.to_numpy(dtype=float)
        if len(years) < min_years:
            return
        slope, _ = np.polyfit(years.astype(float), meds, 1)
        slope = float(slope)
        unit_str = f" {units}/año" if units else "/año"
        if max_trend_per_year is not None and abs(slope) >= max_trend_per_year:
            out.append(
                Violation(
                    ViolationSeverity.ERROR,
                    "extreme_annual_trend",
                    f"'{variable_name}'{group_label}: pendiente mediana anual "
                    f"~{slope:+.3f}{unit_str} (umbral error ±{max_trend_per_year}). "
                    "Posible deriva de calibración o mezcla de fuentes.",
                    {"slope_per_year": slope, "variable": variable_name, "threshold": max_trend_per_year},
                )
            )
        elif warn_trend_per_year is not None and abs(slope) >= warn_trend_per_year:
            out.append(
                Violation(
                    ViolationSeverity.WARNING,
                    "notable_annual_trend",
                    f"'{variable_name}'{group_label}: tendencia notable "
                    f"~{slope:+.3f}{unit_str} (umbral aviso ±{warn_trend_per_year}). "
                    "Puede ser señal real o mezcla de fuentes; requiere revisión.",
                    {"slope_per_year": slope, "variable": variable_name, "threshold": warn_trend_per_year},
                )
            )

    if col_id and col_id in df.columns:
        for gid, g in work.groupby(col_id, dropna=False):
            _check_group(g, f" [{col_id}={gid}]")
    else:
        _check_group(work, "")

    return out


# ---------------------------------------------------------------------------
# Función principal: ejecuta todas las reglas genéricas a la vez
# ---------------------------------------------------------------------------


def run_generic_contract(
    df: pd.DataFrame,
    *,
    col_time: str,
    col_value: str,
    col_id: str | None = None,
    variable_name: str = "valor",
    units: str = "",
    thresholds: GenericContractThresholds | None = None,
) -> list[Violation]:
    """
    Ejecuta el contrato genérico completo sobre un DataFrame.

    Parámetros
    ----------
    df
        DataFrame con al menos ``col_time`` y ``col_value``.
    col_time
        Nombre de la columna temporal (se convierte a datetime).
    col_value
        Nombre de la columna con los valores a validar.
    col_id
        Columna de agrupación (estación, sensor, campaña…). Si es ``None``,
        las reglas se aplican sobre toda la serie.
    variable_name
        Nombre legible de la variable (aparece en los mensajes).
    units
        Unidades de la variable (aparece en los mensajes de rango y tendencia).
    thresholds
        Umbrales; si es ``None`` se usan ``DEFAULT_GENERIC_THRESHOLDS``.

    Retorna
    -------
    list[Violation]
        Errores primero, avisos después (mismo orden que ``radial_contract``).

    Ejemplo de uso (dominio oceánico)
    ----------------------------------
    >>> from ieo.validation.generic_series_contract import (
    ...     GenericContractThresholds, run_generic_contract
    ... )
    >>> th = GenericContractThresholds(
    ...     abs_min=-2.0, abs_max=32.0,
    ...     max_gap_days=90,
    ...     warn_trend_per_year=0.25,
    ...     max_trend_per_year=0.6,
    ... )
    >>> violations = run_generic_contract(
    ...     df, col_time="fecha", col_value="temperatura_c",
    ...     col_id="estacion", variable_name="temperatura", units="°C",
    ...     thresholds=th,
    ... )
    """
    th = thresholds or DEFAULT_GENERIC_THRESHOLDS
    vals = df[col_value].to_numpy(dtype=float) if col_value in df.columns else np.array([], dtype=float)

    violations: list[Violation] = []

    # Regla 1: rango absoluto
    violations.extend(
        check_absolute_range(
            vals,
            abs_min=th.abs_min,
            abs_max=th.abs_max,
            variable_name=variable_name,
            units=units,
        )
    )

    # Regla 2: marcas de tiempo duplicadas
    violations.extend(
        check_duplicate_timestamps(
            df,
            col_time=col_time,
            col_id=col_id,
            variable_name=variable_name,
        )
    )

    # Regla 3: brechas temporales
    if th.max_gap_days is not None:
        violations.extend(
            check_time_gaps(
                df,
                col_time=col_time,
                col_id=col_id,
                max_gap_days=th.max_gap_days,
                variable_name=variable_name,
            )
        )

    # Regla 4: tendencia interanual
    violations.extend(
        check_extreme_trend(
            df,
            col_time=col_time,
            col_value=col_value,
            col_id=col_id,
            warn_trend_per_year=th.warn_trend_per_year,
            max_trend_per_year=th.max_trend_per_year,
            min_years=th.min_years_for_trend,
            variable_name=variable_name,
            units=units,
        )
    )

    return sorted(violations, key=_violations_sort_key)

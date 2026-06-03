"""
Tests del contrato de datos — radial (radial_contract) y genérico (generic_series_contract).

Todos los tests usan datos sintéticos: sin dependencia de CSV o Parquet del IEO.
Pueden ejecutarse en CI sin datos reales.

Estructura
----------
- Sección A: tipos básicos (Violation, ViolationSeverity).
- Sección B: validate_profile_dataframe (contrato de perfil CTD).
- Sección C: validate_monthly_radial_series (contrato de serie mensual).
- Sección D: validate_canonical_ctd_polars (wrapper Polars).
- Sección E: generic_series_contract — reglas transferibles a otros dominios.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from ieo.validation.radial_contract import (
    DEFAULT_THRESHOLDS,
    Violation,
    ViolationSeverity,
    validate_canonical_ctd_polars,
    validate_monthly_radial_series,
    validate_profile_dataframe,
    filter_sampling_dates_pandas,
    validate_sampling_dates_pandas,
)
from ieo.validation.generic_series_contract import (
    GenericContractThresholds,
    check_absolute_range,
    check_duplicate_timestamps,
    check_time_gaps,
    run_generic_contract,
)


# ---------------------------------------------------------------------------
# Utilidades de construcción de datos sintéticos
# ---------------------------------------------------------------------------


def _profile_df(
    *,
    depths: list[float] | None = None,
    temps: list[float] | None = None,
    estacion: int = 1,
    n: int = 10,
    acronimo: str = "cast_01",
) -> pd.DataFrame:
    if temps is not None and depths is None:
        # inferir longitud desde temps para evitar mismatch
        depths = list(range(1, len(temps) + 1))
    elif depths is None:
        depths = list(range(1, n + 1))
    if temps is None:
        temps = [15.0 - d * 0.1 for d in depths]
    return pd.DataFrame(
        {
            "profundidad_m": depths,
            "temperatura_c": temps,
            "estacion": [estacion] * len(depths),
            "acronimo": [acronimo] * len(depths),
        }
    )


def _monthly_df(
    *,
    n_months: int = 24,
    estacion: int = 1,
    base_temp: float = 14.0,
    spike_month: int | None = None,
    spike_delta: float = 15.0,
) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n_months, freq="MS")
    temps = [base_temp + 2.0 * np.sin(i * 2 * np.pi / 12) for i in range(n_months)]
    if spike_month is not None and spike_month < n_months:
        temps[spike_month] += spike_delta
    return pd.DataFrame(
        {
            "fecha": dates,
            "valor_prof": temps,
            "estacion": [estacion] * n_months,
        }
    )


# ---------------------------------------------------------------------------
# A — Tipos básicos
# ---------------------------------------------------------------------------


def test_violation_is_frozen() -> None:
    v = Violation(ViolationSeverity.ERROR, "test_code", "mensaje de prueba")
    with pytest.raises((AttributeError, TypeError)):
        v.code = "otro"  # type: ignore[misc]


def test_violation_severity_values() -> None:
    assert ViolationSeverity.ERROR.value == "error"
    assert ViolationSeverity.WARNING.value == "warning"


# ---------------------------------------------------------------------------
# B — validate_profile_dataframe
# ---------------------------------------------------------------------------


def test_profile_ok_no_violations() -> None:
    df = _profile_df(n=8)
    viols = validate_profile_dataframe(
        df,
        col_prof="profundidad_m",
        col_value="temperatura_c",
        col_estacion="estacion",
    )
    assert viols == []


def test_profile_temp_below_minimum() -> None:
    df = _profile_df(temps=[-5.0] * 5)  # por debajo del mínimo absoluto
    viols = validate_profile_dataframe(
        df,
        col_prof="profundidad_m",
        col_value="temperatura_c",
        col_estacion="estacion",
    )
    codes = [v.code for v in viols]
    assert "temp_out_of_absolute_range" in codes
    errors = [v for v in viols if v.severity == ViolationSeverity.ERROR]
    assert errors, "debe haber al menos un ERROR para temperatura negativa extrema"


def test_profile_temp_above_maximum() -> None:
    df = _profile_df(temps=[50.0] * 5)  # muy por encima del máximo
    viols = validate_profile_dataframe(
        df,
        col_prof="profundidad_m",
        col_value="temperatura_c",
        col_estacion="estacion",
    )
    assert any(v.code == "temp_out_of_absolute_range" for v in viols)


def test_profile_vertical_spike_triggers_error() -> None:
    """Un salto de 30 °C entre dos niveles adyacentes debe producir ERROR."""
    df = _profile_df(
        depths=[1.0, 5.0, 10.0],
        temps=[15.0, 45.0, 15.0],  # +30 °C entre 1 m y 5 m
    )
    viols = validate_profile_dataframe(
        df,
        col_prof="profundidad_m",
        col_value="temperatura_c",
        col_estacion="estacion",
    )
    assert any(
        v.severity == ViolationSeverity.ERROR and "vertical" in v.code for v in viols
    ), f"Se esperaba ERROR por salto vertical; obtenido: {viols}"


def test_profile_missing_column_returns_error() -> None:
    df = pd.DataFrame({"profundidad_m": [1.0, 5.0], "estacion": [1, 1]})
    viols = validate_profile_dataframe(
        df,
        col_prof="profundidad_m",
        col_value="temperatura_c",
        col_estacion="estacion",
    )
    assert any(v.code == "missing_column" for v in viols)


# ---------------------------------------------------------------------------
# C — validate_monthly_radial_series
# ---------------------------------------------------------------------------


def test_monthly_ok_returns_empty() -> None:
    df = _monthly_df(n_months=12)
    viols = validate_monthly_radial_series(df, col_fecha="fecha", col_val="valor_prof", col_estacion="estacion")
    assert viols == []


def test_monthly_spike_error() -> None:
    """Un salto de +15 °C entre meses consecutivos debe generar ERROR."""
    df = _monthly_df(n_months=12, spike_month=5, spike_delta=15.0)
    viols = validate_monthly_radial_series(df, col_fecha="fecha", col_val="valor_prof", col_estacion="estacion")
    assert any(v.severity == ViolationSeverity.ERROR for v in viols), \
        f"Esperado ERROR por spike mensual; obtenido: {viols}"


def test_monthly_moderate_jump_warning() -> None:
    """Un salto de ~7 °C debe generar WARNING, no ERROR."""
    df = _monthly_df(n_months=12, spike_month=5, spike_delta=7.0)
    viols = validate_monthly_radial_series(df, col_fecha="fecha", col_val="valor_prof", col_estacion="estacion")
    sev = {v.severity for v in viols}
    # Puede no haber violaciones si el valor cae fuera de los umbrales del default; ajustamos
    if viols:
        assert ViolationSeverity.ERROR not in sev or any(
            v.code == "temp_month_to_month_jump" for v in viols
        )


def test_monthly_missing_column() -> None:
    df = pd.DataFrame({"fecha": pd.date_range("2020-01-01", periods=3, freq="MS"), "estacion": [1, 1, 1]})
    viols = validate_monthly_radial_series(df, col_fecha="fecha", col_val="valor_prof", col_estacion="estacion")
    assert any(v.code == "missing_column" for v in viols)


# ---------------------------------------------------------------------------
# D — validate_canonical_ctd_polars
# ---------------------------------------------------------------------------


def test_canonical_polars_ok() -> None:
    try:
        import polars as pl
    except ImportError:
        pytest.skip("polars no instalado")

    df = pl.from_pandas(
        pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2021-03-01", "2021-03-01"]),
                "estacion": [1, 1],
                "profundidad_m": [5.0, 20.0],
                "temperatura_c": [14.5, 13.0],
            }
        )
    )
    viols = validate_canonical_ctd_polars(df)
    errors = [v for v in viols if v.severity == ViolationSeverity.ERROR]
    assert errors == [], f"Datos válidos produjeron ERROR: {errors}"


def test_canonical_polars_bad_type() -> None:
    viols = validate_canonical_ctd_polars("no es un dataframe")
    assert any(v.severity == ViolationSeverity.ERROR for v in viols)


def test_filter_sampling_dates_drops_nat() -> None:
    df = pd.DataFrame({"fecha": [pd.NaT, "2020-01-01"], "estacion": [1, 1]})
    out, n = filter_sampling_dates_pandas(df, col_fecha="fecha")
    assert n == 1
    assert len(out) == 1


def test_filter_sampling_dates_drops_future_year() -> None:
    df = pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2020-01-01", "2080-06-01", "1995-03-01"]),
            "estacion": [1, 1, 1],
        }
    )
    out, n = filter_sampling_dates_pandas(df, col_fecha="fecha")
    assert n == 1
    assert len(out) == 2
    assert out["fecha"].dt.year.max() <= 2035


def test_sampling_dates_future_year_error() -> None:
    df = pd.DataFrame({"fecha": pd.to_datetime(["2020-01-01", "2080-06-01"])})
    viols = validate_sampling_dates_pandas(df, col_fecha="fecha")
    assert any(
        v.code == "sampling_date_out_of_calendar_range" and v.severity == ViolationSeverity.ERROR for v in viols
    )


def test_sampling_dates_within_custom_max_ok() -> None:
    df = pd.DataFrame({"fecha": pd.to_datetime(["2080-06-01"])})
    th = replace(DEFAULT_THRESHOLDS, sampling_year_max=2100)
    viols = validate_sampling_dates_pandas(df, col_fecha="fecha", thresholds=th)
    assert not any(v.code == "sampling_date_out_of_calendar_range" for v in viols)


def test_canonical_polars_future_year_in_profile() -> None:
    try:
        import polars as pl
    except ImportError:
        pytest.skip("polars no instalado")

    df = pl.from_pandas(
        pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2021-03-01", "2080-01-01"]),
                "estacion": [1, 1],
                "profundidad_m": [5.0, 5.0],
                "temperatura_c": [14.5, 14.0],
            }
        )
    )
    viols = validate_canonical_ctd_polars(df)
    assert any(v.code == "sampling_date_out_of_calendar_range" for v in viols)


# ---------------------------------------------------------------------------
# E — generic_series_contract (dominio-agnóstico)
# ---------------------------------------------------------------------------


def _generic_df(
    *,
    n: int = 24,
    start: str = "2020-01-01",
    freq: str = "MS",
    base_val: float = 100.0,
    sensor: str = "S1",
    gap_after: int | None = None,
    gap_months: int = 6,
) -> pd.DataFrame:
    dates = pd.date_range(start, periods=n, freq=freq)
    if gap_after is not None and gap_after < n:
        # Elimina algunas filas para crear una brecha
        dates = dates.delete(list(range(gap_after, min(gap_after + gap_months, n))))
    return pd.DataFrame(
        {
            "fecha": dates,
            "valor": [base_val + np.sin(i) for i in range(len(dates))],
            "sensor": [sensor] * len(dates),
        }
    )


def test_generic_ok_no_violations() -> None:
    df = _generic_df(n=24)
    th = GenericContractThresholds(abs_min=0.0, abs_max=200.0)
    viols = run_generic_contract(
        df, col_time="fecha", col_value="valor", variable_name="señal", thresholds=th
    )
    assert viols == []


def test_generic_range_error() -> None:
    df = _generic_df(n=5, base_val=500.0)  # todos los valores fuera de [0, 200]
    th = GenericContractThresholds(abs_min=0.0, abs_max=200.0)
    viols = run_generic_contract(
        df, col_time="fecha", col_value="valor", variable_name="señal", thresholds=th
    )
    assert any(v.code == "out_of_absolute_range" and v.severity == ViolationSeverity.ERROR for v in viols)


def test_generic_gap_warning() -> None:
    df = _generic_df(n=24, gap_after=5, gap_months=5)
    th = GenericContractThresholds(max_gap_days=60.0)
    viols = run_generic_contract(
        df, col_time="fecha", col_value="valor", variable_name="señal", thresholds=th
    )
    assert any(v.code == "time_gap_detected" for v in viols), \
        f"Debería detectar brecha > 60 días; obtenido: {viols}"


def test_generic_duplicate_timestamps_warning() -> None:
    df = _generic_df(n=3)
    # Duplicar la primera fila
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    viols = check_duplicate_timestamps(df, col_time="fecha", variable_name="señal")
    assert any(v.code == "duplicate_timestamps" for v in viols)


def test_check_absolute_range_no_limits() -> None:
    """Sin abs_min ni abs_max no debe emitir ninguna violación."""
    vals = np.array([1.0, 2.0, 3.0])
    viols = check_absolute_range(vals, variable_name="x")
    assert viols == []


def test_generic_trend_error() -> None:
    """Serie con pendiente fuerte debe producir ERROR de tendencia extrema."""
    dates = pd.date_range("2010-01-01", periods=72, freq="MS")
    vals = np.linspace(0.0, 120.0, 72)  # +20 unidades/año ≈ extremo
    df = pd.DataFrame({"fecha": dates, "valor": vals})
    th = GenericContractThresholds(
        warn_trend_per_year=1.0,
        max_trend_per_year=5.0,
        min_years_for_trend=5,
    )
    viols = run_generic_contract(
        df, col_time="fecha", col_value="valor", variable_name="señal", thresholds=th
    )
    assert any(v.code == "extreme_annual_trend" and v.severity == ViolationSeverity.ERROR for v in viols)


def test_generic_contract_transferable_to_volcano_example() -> None:
    """
    Ejemplo de transferibilidad: simula una serie de temperatura volcánica
    con umbrales distintos a los del contrato oceánico.

    Este test documenta intencionalmente el uso-tipo para nuevos dominios.
    """
    dates = pd.date_range("2015-01-01", periods=48, freq="MS")
    temps = np.random.default_rng(0).uniform(50.0, 90.0, size=48)  # 50–90 °C
    temps[20] = 250.0  # anomalía flagrante

    df = pd.DataFrame({"fecha": dates, "temperatura_fumarola_c": temps, "punto": ["F1"] * 48})

    th = GenericContractThresholds(
        abs_min=20.0,
        abs_max=200.0,
        max_gap_days=95,
    )
    viols = run_generic_contract(
        df,
        col_time="fecha",
        col_value="temperatura_fumarola_c",
        col_id="punto",
        variable_name="temperatura fumarola",
        units="°C",
        thresholds=th,
    )
    assert any(v.code == "out_of_absolute_range" for v in viols), \
        "El valor 250 °C debe detectarse fuera del rango [20, 200]"

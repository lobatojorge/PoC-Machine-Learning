"""Validación / contrato de datos para radiales (perfil + serie mensual) y genérico."""

from .radial_contract import (
    Violation,
    ViolationSeverity,
    format_violations_markdown,
    infer_variable_kind,
    validate_canonical_ctd_polars,
    validate_monthly_radial_series,
    validate_profile_dataframe,
)
from .generic_series_contract import (
    GenericContractThresholds,
    run_generic_contract,
)

__all__ = [
    # Tipos comunes
    "Violation",
    "ViolationSeverity",
    # Contrato radial (dominio CTD)
    "format_violations_markdown",
    "infer_variable_kind",
    "validate_canonical_ctd_polars",
    "validate_monthly_radial_series",
    "validate_profile_dataframe",
    # Contrato genérico (transferible a otros dominios)
    "GenericContractThresholds",
    "run_generic_contract",
]

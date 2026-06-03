"""
Variables de entorno del alcance del pipeline (misma cadena de validación para todas las radiales).

- Por defecto no se define alcance: entran **todas** las radiales clasificables.
- ``IEO_PIPELINE_RADIAL=<id>`` acota a una radial concreta (mismo control previo, Parquet, contrato e IF).
- ``IEO_ONLY_CUDILLERO=1`` se mantiene como alias de ``IEO_PIPELINE_RADIAL=cudillero`` (compatibilidad).
"""

from __future__ import annotations

import os
from typing import Final

from ieo.radiales_catalog import RADIAL_STATION_CODES

PIPELINE_RADIAL_ENV: Final[str] = "IEO_PIPELINE_RADIAL"
LEGACY_ONLY_CUDILLERO_ENV: Final[str] = "IEO_ONLY_CUDILLERO"
LEGACY_ALL_RADIALS_ENV: Final[str] = "IEO_ALL_RADIALS"

ALLOWED_PIPELINE_RADIAL_IDS: Final[frozenset[str]] = frozenset(RADIAL_STATION_CODES.keys())


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def allowed_pipeline_radials_csv() -> str:
    return ", ".join(sorted(ALLOWED_PIPELINE_RADIAL_IDS))


def resolve_pipeline_scope() -> tuple[str | None, list[str], str | None]:
    """
    Devuelve ``(radial_id | None, avisos, error)``.

    - ``radial_id`` ``None`` → procesar todas las radiales detectadas.
    - ``error`` no vacío → valor ilegal en ``IEO_PIPELINE_RADIAL``; el caller debe abortar la ejecución.
    """
    warnings: list[str] = []
    raw = os.environ.get(PIPELINE_RADIAL_ENV, "").strip().lower()
    only_cud = _env_truthy(LEGACY_ONLY_CUDILLERO_ENV)
    legacy_all = _env_truthy(LEGACY_ALL_RADIALS_ENV)

    if raw and raw not in ALLOWED_PIPELINE_RADIAL_IDS:
        return (
            None,
            [],
            f"{PIPELINE_RADIAL_ENV}={raw!r} no es un id válido. Use uno de: {allowed_pipeline_radials_csv()}.",
        )

    if raw and only_cud and raw != "cudillero":
        warnings.append(
            f"Aviso: {LEGACY_ONLY_CUDILLERO_ENV}=1 junto con {PIPELINE_RADIAL_ENV}={raw}; "
            f"se aplica el alcance de {PIPELINE_RADIAL_ENV}."
        )
    elif raw == "cudillero" and only_cud:
        warnings.append(
            f"Nota: {LEGACY_ONLY_CUDILLERO_ENV}=1 es redundante con {PIPELINE_RADIAL_ENV}=cudillero."
        )

    if raw:
        if legacy_all:
            warnings.append(
                f"Nota: {LEGACY_ALL_RADIALS_ENV}=1 es redundante cuando el alcance ya está acotado "
                f"por {PIPELINE_RADIAL_ENV}."
            )
        return raw, warnings, None

    if only_cud:
        if legacy_all:
            warnings.append(
                f"Aviso: {LEGACY_ONLY_CUDILLERO_ENV}=1 e {LEGACY_ALL_RADIALS_ENV}=1 a la vez; "
                "se aplica alcance Cudillero."
            )
        return "cudillero", warnings, None

    if legacy_all:
        warnings.append(
            f"Nota: {LEGACY_ALL_RADIALS_ENV}=1 es redundante (por defecto ya se procesan todas las radiales)."
        )

    return None, warnings, None


def is_scoped_pipeline(filtro_radial: str) -> bool:
    """True si la corrida no es «todas las radiales»."""
    return filtro_radial != "todas"

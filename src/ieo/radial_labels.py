"""
Etiquetas en español para radial_id (ingesta, consola, RESUMEN_ULTIMA).
"""

from __future__ import annotations

from ieo.radiales_catalog import (
    RADIAL_ID_CORUNA,
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_GIJON,
    RADIAL_ID_SANTANDER,
    RADIAL_ID_VIGO,
)

RADIAL_LABELS_ES: dict[str, str] = {
    RADIAL_ID_CUDILLERO: "Cudillero",
    RADIAL_ID_GIJON: "Gijón",
    RADIAL_ID_SANTANDER: "Santander",
    RADIAL_ID_CORUNA: "A Coruña",
    RADIAL_ID_VIGO: "Vigo",
    "desconocida": "Sin clasificar",
}


def label_es(radial_id: str) -> str:
    return RADIAL_LABELS_ES.get(radial_id, radial_id)

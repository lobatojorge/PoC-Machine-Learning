"""
ieo
===

Backend del pipeline (producción) para:
- Ingesta escalable (CNV hoy; NetCDF mañana).
- Transformación a un esquema canónico CTD.
- Observabilidad, detección de anomalías y registro inmutable.
- Generación de reportes estáticos por corrida (HTML + JSON).

Nota práctica para usuarios no técnicos
--------------------------------------
Si ejecutas el pipeline, verás una carpeta nueva en `outputs/runs/<run_id>/`.
Ahí encontrarás:
- qué se hizo en cada paso
- qué falló (si algo falla)
- y los ficheros finales listos para usar (Parquet)
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"


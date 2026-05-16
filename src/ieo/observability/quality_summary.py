from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass(frozen=True, slots=True)
class DatasetHealth:
    """
    Resumen de salud del dataset.

    Explicación práctica
    --------------------
    Esto no es “ML”: es un resumen legible para gestión:
    - cuántos datos entraron
    - cuántos quedaron en limpio
    - cuántos se marcaron como sospechosos
    - si faltan columnas clave
    """

    metrics: dict[str, Any]


def build_health_summary(
    *,
    canonical: pl.DataFrame,
    clean: pl.DataFrame,
    anomalies: pl.DataFrame,
    audit_log: pl.DataFrame,
) -> DatasetHealth:
    n_in = int(canonical.height)
    n_clean = int(clean.height)
    n_anom = int(anomalies.height)
    frac_anom = float(n_anom / n_in) if n_in else 0.0

    required = ["fecha", "estacion", "cast", "profundidad_m", "temperatura_c"]
    missing_required = [c for c in required if c not in canonical.columns]

    # Completitud (simple): % de nulos por columna (top 10)
    null_fracs: dict[str, float] = {}
    for c in canonical.columns:
        try:
            null_fracs[c] = float(canonical.select(pl.col(c).is_null().mean()).item())
        except Exception:
            continue
    top_nulls = sorted(null_fracs.items(), key=lambda kv: -kv[1])[:10]

    return DatasetHealth(
        metrics={
            "n_rows_in": n_in,
            "n_rows_clean": n_clean,
            "n_rows_anomalies": n_anom,
            "fraction_anomalies": frac_anom,
            "missing_required_columns": missing_required,
            "top_null_fractions": [{"column": k, "null_fraction": v} for k, v in top_nulls],
            "audit_log_rows": int(audit_log.height),
        }
    )


"""Serie mensual por estación interpolando un perfil CTD a profundidad objetivo."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monthly_value_at_depth(
    df: pd.DataFrame,
    *,
    col_fecha: str = "fecha",
    col_prof: str = "profundidad_m",
    col_value: str,
    col_estacion: str = "estacion",
    target_depth_m: float = 5.0,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    """
    Interpola ``col_value`` a ``target_depth_m`` por lance y agrega media mensual por estación.

    Returns:
        DataFrame con columnas ``estacion``, ``fecha``, ``valor_prof`` y diagnóstico de lances.
    """
    use_cols = [col_fecha, col_prof, col_value, col_estacion] + (["acronimo"] if "acronimo" in df.columns else [])
    work = df[use_cols].copy()
    work[col_fecha] = pd.to_datetime(work[col_fecha], errors="coerce")
    work[col_prof] = pd.to_numeric(work[col_prof], errors="coerce")
    work[col_value] = pd.to_numeric(work[col_value], errors="coerce")
    work[col_estacion] = pd.to_numeric(work[col_estacion], errors="coerce")
    work = work.dropna(subset=[col_fecha, col_prof, col_value, col_estacion])
    if work.empty:
        return pd.DataFrame(), {
            "n_casts": 0,
            "n_casts_con_valor": 0,
            "n_casts_sin_cobertura_en_profundidad": 0,
            "profundidad_objetivo_m": int(target_depth_m)
            if target_depth_m == int(target_depth_m)
            else target_depth_m,
        }

    if "acronimo" in work.columns:
        group_keys = ["acronimo", col_estacion]
    else:
        work["_fecha_d"] = work[col_fecha].dt.date
        group_keys = ["_fecha_d", col_estacion]

    def _interp_value(profile: pd.DataFrame) -> float:
        dft = (
            pd.DataFrame(
                {
                    "z": profile[col_prof].to_numpy(dtype=float),
                    "v": profile[col_value].to_numpy(dtype=float),
                }
            )
            .dropna()
            .groupby("z", as_index=False)["v"]
            .mean()
            .sort_values("z")
        )
        if dft.empty:
            return float("nan")
        z = dft["z"].to_numpy(dtype=float)
        v = dft["v"].to_numpy(dtype=float)
        if target_depth_m < float(z[0]) or target_depth_m > float(z[-1]):
            return float("nan")
        return float(np.interp(target_depth_m, z, v))

    per_cast = (
        work.groupby(group_keys, as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "fecha": pd.to_datetime(g[col_fecha].iloc[0]).to_period("M").to_timestamp(how="start"),
                    "valor_prof": _interp_value(g),
                }
            ),
            include_groups=False,
        )
        .reset_index(drop=True)
    )
    n_casts = int(len(per_cast))
    n_valid = int(per_cast["valor_prof"].notna().sum())
    diag: dict[str, float | int] = {
        "n_casts": n_casts,
        "n_casts_con_valor": n_valid,
        "n_casts_sin_cobertura_en_profundidad": n_casts - n_valid,
        "profundidad_objetivo_m": int(target_depth_m) if target_depth_m == int(target_depth_m) else target_depth_m,
    }

    per_cast = per_cast.dropna(subset=["valor_prof", "fecha"])
    if per_cast.empty:
        return pd.DataFrame(), diag

    agg = per_cast.groupby([col_estacion, "fecha"], as_index=False)["valor_prof"].mean()
    agg = agg.loc[:, [col_estacion, "fecha", "valor_prof"]]
    return agg.sort_values([col_estacion, "fecha"]).reset_index(drop=True), diag

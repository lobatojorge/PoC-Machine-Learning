from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

# Columnas categóricas/de identificador que NO deben usarse como features numéricas en el IF.
# Aunque vengan como Int/Float en el Parquet, no tienen distancia métrica significativa.
_CATEGORICAL_ID_COLS: frozenset[str] = frozenset(
    {"estacion", "acronimo", "cast", "source_file", "radial_id", "run_id", "row_id"}
)

# Si una columna tiene más de este porcentaje de NaN, se excluye de las features.
# Configurable: IEO_IF_MAX_NAN_FRACTION (float, 0.0–0.99). Default: 0.40.
_MAX_NAN_FRACTION_FOR_FEATURE: float = float(
    os.environ.get("IEO_IF_MAX_NAN_FRACTION", "0.40")
)

# Valor fijo del pipeline (paso 02). Ver README y docs/arquitectura_validacion_datos.md.
# Configurable: IEO_IF_CONTAMINATION (float, 0.01–0.50). Default: 0.05.
IF_CONTAMINATION: float = float(
    os.environ.get("IEO_IF_CONTAMINATION", "0.05")
)


@dataclass(frozen=True, slots=True)
class IsolationForestConfig:
    """
    Configuración del detector de anomalías.

    Explicación práctica
    --------------------
    - `random_state`: hace que el resultado sea repetible.
    - `contamination`: proporción de filas atípicas esperadas por estrato (0.0–0.5).
      El pipeline de producción usa ``IF_CONTAMINATION`` (**0.05**, 5 %). También
      admite ``"auto"`` (≈10 % en sklearn) si se instancia la config manualmente.
    - `stratify_by_radial`: si True (por defecto), entrena un modelo separado
      por cada valor de ``radial_id`` presente en el dataframe.
    - `depth_bands_m`: rangos de profundidad (metros) para estratificar el IF.
      Dentro de cada radial, se entrenará un modelo por banda.
    """

    contamination: float | str = IF_CONTAMINATION
    random_state: int = 42
    n_estimators: int = 200
    max_features: float | int = 1.0
    stratify_by_radial: bool = True
    depth_bands_m: tuple[tuple[float, float], ...] = (
        (0.0, 20.0),
        (20.0, 100.0),
        (100.0, float("inf")),
    )


@dataclass(frozen=True, slots=True)
class AnomalyOutputs:
    clean: pl.DataFrame
    anomalies: pl.DataFrame
    audit_log: pl.DataFrame
    metrics: dict[str, Any]


def _select_numeric_feature_columns(
    df: pl.DataFrame,
    *,
    exclude: set[str],
    max_nan_fraction: float = _MAX_NAN_FRACTION_FOR_FEATURE,
) -> list[str]:
    """
    Selecciona columnas numéricas válidas para el IF.

    Exclusiones automáticas:
    - Columnas en `exclude` (IDs de fila, claves de auditoría).
    - Columnas categóricas/de identificador aunque sean numéricas (estacion, cast, etc.).
    - Columnas con más del `max_nan_fraction` de valores NaN (imputación poco fiable).
    """
    numeric_dtypes = (
        pl.Int8, pl.Int16, pl.Int32, pl.Int64,
        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        pl.Float32, pl.Float64,
    )
    cols: list[str] = []
    n_rows = df.height
    for name, dtype in df.schema.items():
        if name in exclude:
            continue
        if name.lower() in _CATEGORICAL_ID_COLS:
            continue
        if dtype not in numeric_dtypes:
            continue
        # Comprobar fracción de NaN
        if n_rows > 0:
            n_null = df[name].null_count()
            if n_null / n_rows > max_nan_fraction:
                continue
        cols.append(name)
    return cols


def _robust_feature_explanation(
    *,
    x: np.ndarray,
    feature_names: list[str],
    top_k: int = 5,
) -> list[list[str]]:
    """
    Explicación simple por fila: "qué variables se salen más".

    Técnica:
    - Calculamos z-score robusto aproximado usando mediana y MAD.
    - Devolvemos top-K features por |z|.
    """

    if x.size == 0 or not feature_names:
        return [[] for _ in range(x.shape[0])]

    med = np.nanmedian(x, axis=0)
    mad = np.nanmedian(np.abs(x - med), axis=0)
    mad = np.where(mad < 1e-12, 1.0, mad)
    z = (x - med) / mad
    zabs = np.abs(z)
    idx = np.argsort(-zabs, axis=1)[:, : max(1, int(top_k))]
    out: list[list[str]] = []
    for i in range(x.shape[0]):
        out.append([feature_names[int(j)] for j in idx[i]])
    return out


def _run_isolation_forest_on_matrix(
    x: np.ndarray,
    *,
    config: IsolationForestConfig,
    n_jobs: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Entrena un IsolationForest sobre la matriz `x` y devuelve (preds, scores)."""
    from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

    model = IsolationForest(
        n_estimators=int(config.n_estimators),
        contamination=config.contamination,
        random_state=int(config.random_state),
        max_features=config.max_features,
        n_jobs=int(n_jobs),
    )
    preds = model.fit_predict(x)
    scores = model.decision_function(x)
    return preds, scores


def _impute_nan_with_median(x: np.ndarray) -> np.ndarray:
    """Imputa NaN con la mediana de la columna; si toda la columna es NaN → 0."""
    col_median = np.nanmedian(x, axis=0)
    col_median = np.where(np.isfinite(col_median), col_median, 0.0)
    inds = np.where(~np.isfinite(x))
    x[inds] = np.take(col_median, inds[1])
    return x


def detect_anomalies_isolation_forest(
    *,
    df: pl.DataFrame,
    row_id_col: str,
    config: IsolationForestConfig,
    run_id: str,
    source_file: str,
    n_jobs: int = -1,
) -> AnomalyOutputs:
    """
    Detecta anomalías y devuelve:
    - clean: filas no anómalas
    - anomalies: filas anómalas
    - audit_log: registro inmutable (por qué / score / threshold / features)

    Mejoras respecto a la versión anterior:
    - `contamination=IF_CONTAMINATION` (0.05) en el pipeline: umbral fijo del 5 % por estrato.
    - Columnas con >40% NaN se excluyen de las features (imputación poco fiable).
    - Columnas categóricas codificadas como enteros (estacion, cast) se excluyen.
    - `top_features` solo se calcula y guarda para filas anómalas (audit más ligero).
    - Estratificación opcional por `radial_id` y banda de profundidad.
    """

    try:
        from sklearn.ensemble import IsolationForest  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise ImportError("Falta scikit-learn para IsolationForest.") from exc

    if df.is_empty():
        empty = pl.DataFrame()
        return AnomalyOutputs(
            clean=empty,
            anomalies=empty,
            audit_log=empty,
            metrics={"n_rows": 0, "n_features": 0, "n_anomalies": 0},
        )

    exclude = {row_id_col}
    feature_cols = _select_numeric_feature_columns(df, exclude=exclude)
    if len(feature_cols) < 2:
        # Sin features suficientes, no hacemos ML: audit explícito.
        audit = df.select(
            [
                pl.lit(run_id).alias("run_id"),
                pl.lit(source_file).alias("source_file"),
                pl.col(row_id_col).alias("row_id"),
                pl.lit(False).alias("is_anomaly"),
                pl.lit(0.0).alias("anomaly_score"),
                pl.lit(None).cast(pl.Float64).alias("threshold"),
                pl.lit("insufficient_features").alias("reason"),
                pl.lit([]).cast(pl.List(pl.String)).alias("top_features"),
            ]
        )
        return AnomalyOutputs(
            clean=df,
            anomalies=pl.DataFrame(),
            audit_log=audit,
            metrics={
                "n_rows": int(df.height),
                "n_features": int(len(feature_cols)),
                "n_anomalies": 0,
                "reason": "insufficient_features",
            },
        )

    # --- Estratificación por radial_id y banda de profundidad ---
    has_radial = "radial_id" in df.columns and config.stratify_by_radial
    depth_col = next(
        (c for c in ("profundidad_m", "pressure", "depth") if c in df.columns and c in feature_cols),
        None,
    )

    # Construir etiquetas de estrato por fila
    n = df.height
    strata: list[str] = ["_all"] * n

    if has_radial or depth_col:
        radials = df["radial_id"].to_list() if has_radial else ["_"] * n
        depths = df[depth_col].to_list() if depth_col else [0.0] * n

        def _depth_band(d: float | None) -> str:
            if d is None or not np.isfinite(d):
                return "unk"
            for lo, hi in config.depth_bands_m:
                if lo <= d < hi:
                    return f"{lo:.0f}-{hi:.0f}"
            return "deep"

        strata = [
            f"{r}|{_depth_band(d)}" for r, d in zip(radials, depths)
        ]

    # Acumular predicciones y scores
    is_anom_all = np.zeros(n, dtype=bool)
    scores_all = np.zeros(n, dtype=float)
    q_all = np.zeros(n, dtype=float)

    unique_strata = list(dict.fromkeys(strata))  # preserva orden
    for stratum in unique_strata:
        idx = [i for i, s in enumerate(strata) if s == stratum]
        if len(idx) < 10:
            # Estrato demasiado pequeño: no entrenamos modelo, marcamos como limpias
            continue
        x = df[feature_cols][idx].to_numpy(dtype=float, fill_value=float("nan")).copy()
        x = _impute_nan_with_median(x)

        preds, scores = _run_isolation_forest_on_matrix(x, config=config, n_jobs=n_jobs)
        q = float(
            np.quantile(scores, float(config.contamination))
            if isinstance(config.contamination, float)
            else np.quantile(scores, IF_CONTAMINATION)
        )
        for list_pos, df_pos in enumerate(idx):
            is_anom_all[df_pos] = preds[list_pos] == -1
            scores_all[df_pos] = scores[list_pos]
            q_all[df_pos] = q

    n_anom = int(is_anom_all.sum())

    # top_features solo para filas anómalas (evita inflar el audit)
    anom_indices = [i for i, a in enumerate(is_anom_all) if a]
    if anom_indices and feature_cols:
        x_full = df.select(feature_cols).to_numpy().copy()
        x_full = _impute_nan_with_median(x_full)
        x_anom = x_full[anom_indices]
        top_feats_anom = _robust_feature_explanation(x=x_anom, feature_names=feature_cols, top_k=5)
    else:
        top_feats_anom = []

    top_feats_all: list[list[str]] = [[] for _ in range(n)]
    for list_pos, df_pos in enumerate(anom_indices):
        top_feats_all[df_pos] = top_feats_anom[list_pos]

    audit = pl.DataFrame(
        {
            "run_id": [run_id] * n,
            "source_file": [source_file] * n,
            "row_id": df[row_id_col].to_list(),
            "is_anomaly": is_anom_all.tolist(),
            "anomaly_score": scores_all.astype(float).tolist(),
            "threshold": q_all.astype(float).tolist(),
            "reason": ["isolation_forest"] * n,
            "top_features": top_feats_all,
        }
    )

    # Adjuntar score a los datasets (útil para depurar)
    df_scored = df.with_columns(
        [
            pl.Series("anomaly_score", scores_all.astype(float).tolist()),
            pl.Series("is_anomaly", is_anom_all.tolist()),
        ]
    )
    clean = df_scored.filter(~pl.col("is_anomaly")).drop("is_anomaly")
    anomalies = df_scored.filter(pl.col("is_anomaly")).drop("is_anomaly")

    return AnomalyOutputs(
        clean=clean,
        anomalies=anomalies,
        audit_log=audit,
        metrics={
            "n_rows": int(n),
            "n_features": int(len(feature_cols)),
            "n_anomalies": int(n_anom),
            "contamination": config.contamination,
            "random_state": int(config.random_state),
            "threshold_score_q": float(np.nanmedian(q_all)),
            "feature_columns": feature_cols,
            "strata": unique_strata,
        },
    )

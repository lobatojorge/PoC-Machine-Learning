from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl


@dataclass(frozen=True, slots=True)
class IsolationForestConfig:
    """
    Configuración del detector de anomalías.

    Explicación práctica
    --------------------
    - `random_state`: hace que el resultado sea repetible.
    - `contamination`: controla cuántas filas “sospechosas” esperamos.
    """

    contamination: float = 0.05
    random_state: int = 42
    n_estimators: int = 200
    max_features: float | int = 1.0


@dataclass(frozen=True, slots=True)
class AnomalyOutputs:
    clean: pl.DataFrame
    anomalies: pl.DataFrame
    audit_log: pl.DataFrame
    metrics: dict[str, Any]


def _select_numeric_feature_columns(df: pl.DataFrame, *, exclude: set[str]) -> list[str]:
    cols: list[str] = []
    for name, dtype in df.schema.items():
        if name in exclude:
            continue
        if dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.Float32, pl.Float64):
            cols.append(name)
    return cols


def _robust_feature_explanation(
    *,
    x: np.ndarray,
    feature_names: list[str],
    top_k: int = 5,
) -> list[list[str]]:
    """
    Explicación simple por fila: “qué variables se salen más”.

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


def detect_anomalies_isolation_forest(
    *,
    df: pl.DataFrame,
    row_id_col: str,
    config: IsolationForestConfig,
    run_id: str,
    source_file: str,
) -> AnomalyOutputs:
    """
    Detecta anomalías y devuelve:
    - clean: filas no anómalas
    - anomalies: filas anómalas
    - audit_log: registro inmutable (por qué / score / threshold / features)
    """

    try:
        from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
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
        # Sin features, no hacemos ML: audit explícito.
        audit = df.select(
            [
                pl.lit(run_id).alias("run_id"),
                pl.lit(source_file).alias("source_file"),
                pl.col(row_id_col).alias("row_id"),
                pl.lit(False).alias("is_anomaly"),
                pl.lit(0.0).alias("anomaly_score"),
                pl.lit(None).cast(pl.Float64).alias("threshold"),
                pl.lit("insufficient_features").alias("reason"),
                pl.lit([]).alias("top_features"),
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

    # Convertir a numpy (sin pandas)
    x = df.select(feature_cols).to_numpy()
    # Imputación simple (mediana por columna)
    col_median = np.nanmedian(x, axis=0)
    # si todo NaN en una columna, nanmedian da NaN -> lo cambiamos a 0
    col_median = np.where(np.isfinite(col_median), col_median, 0.0)
    inds = np.where(~np.isfinite(x))
    x[inds] = np.take(col_median, inds[1])

    model = IsolationForest(
        n_estimators=int(config.n_estimators),
        contamination=float(config.contamination),
        random_state=int(config.random_state),
        max_features=config.max_features,
        n_jobs=-1,
    )
    preds = model.fit_predict(x)
    scores = model.decision_function(x)  # mayor = más normal

    is_anom = preds == -1
    n_anom = int(is_anom.sum())

    # Umbral explícito (score quantile acorde a contamination)
    # Nota: con decision_function, outliers tienden a scores más bajos.
    q = float(np.quantile(scores, float(config.contamination)))

    top_feats = _robust_feature_explanation(x=x, feature_names=feature_cols, top_k=5)

    audit = pl.DataFrame(
        {
            "run_id": [run_id] * df.height,
            "source_file": [source_file] * df.height,
            "row_id": df[row_id_col].to_list(),
            "is_anomaly": is_anom.tolist(),
            "anomaly_score": scores.astype(float).tolist(),
            "threshold": [q] * df.height,
            "reason": ["isolation_forest"] * df.height,
            "top_features": top_feats,
        }
    )

    # Adjuntar score a los datasets (útil para depurar)
    df_scored = df.with_columns(
        [
            pl.Series("anomaly_score", scores.astype(float).tolist()),
            pl.Series("is_anomaly", is_anom.tolist()),
        ]
    )
    clean = df_scored.filter(~pl.col("is_anomaly")).drop("is_anomaly")
    anomalies = df_scored.filter(pl.col("is_anomaly")).drop("is_anomaly")

    return AnomalyOutputs(
        clean=clean,
        anomalies=anomalies,
        audit_log=audit,
        metrics={
            "n_rows": int(df.height),
            "n_features": int(len(feature_cols)),
            "n_anomalies": int(n_anom),
            "contamination": float(config.contamination),
            "random_state": int(config.random_state),
            "threshold_score_q": float(q),
            "feature_columns": feature_cols,
        },
    )


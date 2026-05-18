"""
Módulo de Análisis y Pronóstico Operativo Oceánico (WGMLEARN)
=============================================================

Este script representa el componente `02_analysis.py` de la arquitectura ODA.
Incluye agregación mensual, descomposición Marcos (tendencia + Fourier) y
bandas de incertidumbre iid sobre residuos para el visor (sin modelos AR).

La clase `OceanForecaster` queda como baseline Statsmodels para pronóstico
operativo legacy; el visor Streamlit usa `decompose_marcos_holdout_last_n` y
`marcos_iid_bands_on_residuals`.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Tuple, Optional, Any, Dict
import warnings

# Suprimir avisos molestos de statsmodels/pandas para salida limpia en consola
warnings.filterwarnings("ignore")

import statsmodels.api as sm

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN DE HIPERPARÁMETROS
# ==========================================
FORECAST_HORIZON_YEARS = 5       # Años a predecir hacia el futuro
CONFIDENCE_LEVEL = 0.05           # Alpha para intervalo del 95% (1 - 0.95 = 0.05)
TARGET_VARIABLE = "temperatura"  # Variable principal a pronosticar
FOURIER_K = 3                     # Nº de armónicos (K) para estacionalidad mensual continua
# ==========================================

def monthly_bin_and_anomaly(
    df: pd.DataFrame,
    *,
    col_fecha: str,
    col_valor: str,
) -> pd.DataFrame:
    """
    Construye una serie mensual estricta (MS) y calcula climatología + anomalía.

    Qué resuelve
    ------------
    - **Irregularidad intra-mensual**: si hay varios muestreos en un mes, promedia.
    - **Malla temporal estricta**: fuerza 12 bins/año (freq='MS') reindexando.
    - **Climatología mensual**: media histórica por mes (1..12).
    - **Anomalía mensual**: Valor_t - Climatologia_{mes}.

    Returns
    -------
    DataFrame con columnas:
      - fecha (Timestamp, inicio de mes)
      - <col_valor> (media mensual observada; NaN si mes sin datos)
      - mes (1..12)
      - climatologia_mes (media histórica del mes)
      - anomalia_mensual (valor - climatologia_mes)
    """
    work = df[[col_fecha, col_valor]].copy()
    work[col_fecha] = pd.to_datetime(work[col_fecha], errors="coerce")
    work[col_valor] = pd.to_numeric(work[col_valor], errors="coerce")
    work = work.dropna(subset=[col_fecha, col_valor])
    if work.empty:
        return pd.DataFrame(columns=["fecha", col_valor, "mes", "climatologia_mes", "anomalia_mensual"])

    # Bin mensual: inicio de mes (MS) y media si múltiples muestreos
    work["fecha"] = work[col_fecha].dt.to_period("M").dt.to_timestamp(how="start")
    monthly = work.groupby("fecha", as_index=False)[col_valor].mean()

    # Malla estricta mensual (12 bins/año)
    full_index = pd.date_range(
        start=monthly["fecha"].min(),
        end=monthly["fecha"].max(),
        freq="MS",
    )
    monthly = (
        monthly.set_index("fecha")
        .reindex(full_index)
        .rename_axis("fecha")
        .reset_index()
    )

    monthly["mes"] = monthly["fecha"].dt.month

    # Climatología mensual (12 valores). Se calcula solo con meses con dato.
    clim = monthly.dropna(subset=[col_valor]).groupby("mes")[col_valor].mean()
    monthly["climatologia_mes"] = monthly["mes"].map(clim)
    monthly["anomalia_mensual"] = monthly[col_valor] - monthly["climatologia_mes"]

    return monthly


def _month_index(dates: pd.Series) -> np.ndarray:
    """
    Índice temporal entero (meses desde el primer mes).

    Esto permite usar el modelo de Fourier sobre una escala uniforme:
      t = 0, 1, 2, ... (unidades: meses)
    """
    d = pd.to_datetime(dates, errors="coerce")
    if d.isna().all():
        return np.array([], dtype=int)
    y0 = int(d.min().year)
    m0 = int(d.min().month)
    return ((d.dt.year - y0) * 12 + (d.dt.month - m0)).to_numpy(dtype=int)


def fit_fourier_seasonality(
    df_monthly: pd.DataFrame,
    *,
    col_fecha: str = "fecha",
    col_y: str = "yhat",
    K: int = FOURIER_K,
) -> Dict[str, object]:
    """
    Ajusta un componente estacional continuo mediante armónicos de Fourier.

    Modelo
    ------
      y_t = α + Σ_{k=1..K} [ a_k sin(2π k t / 12) + b_k cos(2π k t / 12) ]

    donde t está en meses (0,1,2,...) y 12 es el periodo anual en meses.

    Devuelve coeficientes y la serie estacional estimada para todas las fechas
    presentes en `df_monthly` (incluye meses sin dato en y).
    """
    work = df_monthly[[col_fecha, col_y]].copy()
    work[col_fecha] = pd.to_datetime(work[col_fecha], errors="coerce")
    work[col_y] = pd.to_numeric(work[col_y], errors="coerce")
    work = work.dropna(subset=[col_fecha])
    if work.empty:
        return {"coef": None, "seasonal": pd.Series(dtype=float)}

    t_all = _month_index(work[col_fecha])
    if t_all.size == 0:
        return {"coef": None, "seasonal": pd.Series(dtype=float)}

    # Construir X(t) para todos los meses
    cols = [np.ones_like(t_all, dtype=float)]
    for k in range(1, int(max(1, K)) + 1):
        w = 2.0 * np.pi * k * t_all / 12.0
        cols.append(np.sin(w))
        cols.append(np.cos(w))
    X_all = np.column_stack(cols)

    # Ajustar solo con y no-nulo (meses observados)
    mask = work[col_y].notna().to_numpy()
    if mask.sum() < (2 * int(max(1, K)) + 1):
        # No hay suficientes puntos para estimar K armónicos + intercepto
        # Fallback: estacionalidad = 0
        seasonal = pd.Series(np.zeros(len(work), dtype=float), index=work[col_fecha])
        return {"coef": None, "seasonal": seasonal}

    y_obs = work.loc[mask, col_y].to_numpy(dtype=float)
    X_obs = X_all[mask, :]
    coef, *_ = np.linalg.lstsq(X_obs, y_obs, rcond=None)

    seasonal_hat = X_all @ coef
    seasonal = pd.Series(seasonal_hat.astype(float), index=work[col_fecha])
    return {"coef": coef, "seasonal": seasonal}


class OceanForecaster:
    """
    Clase modular orientada a objetos para el modelado de series temporales
    oceanográficas. Diseñada con el patrón Strategy para permitir la inyección
    de Foundation Models en el futuro.
    """
    
    def __init__(self, horizon_months: int = FORECAST_HORIZON_YEARS * 12, alpha: float = CONFIDENCE_LEVEL):
        self.horizon: int = int(horizon_months)
        self.alpha: float = alpha
        self.model: Any = None
        self.results: Any = None
        self._fallback_mean: float = 0.0
        self._fallback_std: float = 0.0
        self._last_date: Optional[pd.Timestamp] = None
        
    def _prepare_data(self, df: pd.DataFrame, target: str) -> pd.Series:
        """
        Prepara y asegura la continuidad temporal de la serie.
        """
        ts = df.set_index('fecha')[target].sort_index()
        # Rellenar huecos mensuales (malla estricta ya viene del binning)
        ts = ts.interpolate(method='linear')
        return ts
        
    def fit(self, df: pd.DataFrame, target: str) -> None:
        """
        Entrena el modelo base (SARIMAX baseline).
        
        [!] PUNTO DE ENCHUFE PARA FOUNDATION MODELS:
        Aquí es donde en el futuro se instanciaría el cliente de TimeGPT,
        o se cargarían los pesos pre-entrenados de PatchTST (HuggingFace)
        en lugar del SARIMAX clásico.
        """
        ts = self._prepare_data(df, target)
        
        # Necesitamos un mínimo de datos para que ARIMA/SARIMAX converja
        if len(ts) < 3:
            logger.warning("Histórico demasiado corto para un modelado complejo. Usando fallback basal (Media Variante).")
            self.model = "fallback"
            self._fallback_mean = ts.mean()
            self._fallback_std = ts.std() if len(ts) > 1 else 0.5
            self._last_date = ts.index[-1]
            return

        try:
            # Modelo Baseline: SARIMAX(1, 1, 1) sencillo. 
            # En un entorno de producción, los parámetros (p,d,q) se optimizarían 
            # dinámicamente usando auto_arima.
            self.model = sm.tsa.statespace.SARIMAX(
                ts, 
                order=(1, 1, 1), 
                enforce_stationarity=False, 
                enforce_invertibility=False
            )
            self.results = self.model.fit(disp=False)
        except Exception as e:
            logger.error(f"Error entrenando SARIMAX: {str(e)}. Activando Fallback.")
            self.model = "fallback"
            self._fallback_mean = ts.mean()
            self._fallback_std = ts.std() if len(ts) > 1 else 0.5
            self._last_date = ts.index[-1]

    def predict(self) -> pd.DataFrame:
        """
        Genera el pronóstico futuro con banda de confianza.
        
        Returns:
            pd.DataFrame con columnas [fecha, target, target_lower, target_upper, tipo]
        """
        if self.model == "fallback":
            # Generar fechas futuras (meses)
            future_dates = pd.date_range(
                start=self._last_date + pd.DateOffset(months=1),
                periods=self.horizon, 
                freq='MS'
            )
            
            # Predicción simple: Media móvil amortiguada o flat + ruido
            yhat = [self._fallback_mean] * self.horizon
            margin_error = self._fallback_std * 1.96 # Aprox 95% CI
            
            forecast_df = pd.DataFrame({
                'fecha': future_dates,
                'forecast_mean': yhat,
                'forecast_lower': np.array(yhat) - margin_error,
                'forecast_upper': np.array(yhat) + margin_error
            })
            return forecast_df
            
        # Predicción real usando Statsmodels
        pred = self.results.get_forecast(steps=self.horizon)
        pred_ci = pred.conf_int(alpha=self.alpha)
        
        forecast_df = pd.DataFrame({
            'fecha': pred.predicted_mean.index,
            'forecast_mean': pred.predicted_mean.values,
            'forecast_lower': pred_ci.iloc[:, 0].values,
            'forecast_upper': pred_ci.iloc[:, 1].values
        })
        
        return forecast_df

def process_station_forecast(df_station: pd.DataFrame, station_name: str, target: str) -> pd.DataFrame:
    """
    Ejecuta el ciclo de modelado completo de histórico + pronóstico para una estación.
    """
    # 1. Asegurar formato temporal anual (preferencia: fecha_muestreo -> fecha -> ano/year)
    if "fecha_muestreo" in df_station.columns:
        df_station["fecha"] = pd.to_datetime(df_station["fecha_muestreo"], errors="coerce")
    elif "fecha" in df_station.columns:
        df_station["fecha"] = pd.to_datetime(df_station["fecha"], errors="coerce")
    else:
        year_col = next((c for c in ("ano", "año", "year", "anio", "yy") if c in df_station.columns), None)
        if year_col is not None:
            years = pd.to_numeric(df_station[year_col], errors="coerce")
            df_station["fecha"] = pd.to_datetime(years.astype("Int64").astype(str) + "-06-15", errors="coerce")
        else:
            return pd.DataFrame()

    df_station = df_station.dropna(subset=["fecha"])
    
    if df_station.empty:
        return pd.DataFrame()
        
    # ----------------------------------------------------------
    # (A) BINNING MENSUAL + CLIMATOLOGÍA + ANOMALÍA
    # ----------------------------------------------------------
    monthly = monthly_bin_and_anomaly(df_station, col_fecha="fecha", col_valor=target)
    if monthly.empty:
        return pd.DataFrame()
    monthly["estacion"] = station_name

    # Climatología mensual (12 bins) por estación para aplicar también al pronóstico
    clim_map = (
        monthly.dropna(subset=[target])
        .groupby("mes")[target]
        .mean()
        .to_dict()
    )
    
    # 2. Marcar datos históricos (mensual)
    # Nota: mantenemos `yhat` como nombre estándar de "valor observado/modelado"
    # para compatibilidad con consumidores existentes.
    df_historical = monthly[["fecha", "estacion", target, "mes", "climatologia_mes", "anomalia_mensual"]].copy()
    df_historical["yhat_lower"] = df_historical[target]
    df_historical["yhat_upper"] = df_historical[target]
    df_historical.rename(columns={target: "yhat"}, inplace=True)
    df_historical["tipo_dato"] = "histórico"

    # ----------------------------------------------------------
    # (B) DESESTACIONALIZACIÓN CONTINUA (FOURIER)
    # ----------------------------------------------------------
    fourier_fit = fit_fourier_seasonality(monthly, col_fecha="fecha", col_y=target, K=FOURIER_K)
    seasonal_hist = fourier_fit["seasonal"]
    # Alinear por fecha (inicio de mes)
    df_historical["seasonal_fourier"] = df_historical["fecha"].map(seasonal_hist.to_dict())
    df_historical["temp_deseasonal_fourier"] = df_historical["yhat"] - df_historical["seasonal_fourier"]

    # Anomalía desestacionalizada (centrada a media histórica)
    mu_ds = float(df_historical["temp_deseasonal_fourier"].mean(skipna=True))
    df_historical["anomalia_fourier"] = df_historical["temp_deseasonal_fourier"] - mu_ds
    
    # 3. Modelado Predictivo
    forecaster = OceanForecaster()
    
    # [FEATURE FLAG] En el futuro:
    # forecaster = DeepOceanForecaster(foundation_model="TimeGPT")
    
    # 3. Modelado Predictivo (mensual): usa serie `yhat` (observada mensual) como target
    df_model = monthly[["fecha", target]].copy()
    forecaster.fit(df_model, target)
    df_future = forecaster.predict()
    
    # 4. Formatear y alinear DataFrame del pronóstico
    df_future['estacion'] = station_name
    df_future.rename(columns={
        'forecast_mean': 'yhat',
        'forecast_lower': 'yhat_lower',
        'forecast_upper': 'yhat_upper'
    }, inplace=True)
    df_future['tipo_dato'] = 'pronóstico'

    df_future["mes"] = df_future["fecha"].dt.month
    df_future["climatologia_mes"] = df_future["mes"].map(clim_map)
    df_future["anomalia_mensual"] = df_future["yhat"] - df_future["climatologia_mes"]

    # Fourier también para el futuro: extrapola el componente estacional
    # usando el mismo ajuste (t en meses desde el inicio de la serie histórica).
    if isinstance(fourier_fit.get("coef", None), np.ndarray):
        coef = fourier_fit["coef"]  # type: ignore[assignment]
        # construir t para futuro con el mismo origen (primer mes del monthly)
        origin = pd.to_datetime(monthly["fecha"].min())
        t_future = ((df_future["fecha"].dt.year - origin.year) * 12 + (df_future["fecha"].dt.month - origin.month)).to_numpy(dtype=int)
        cols_f = [np.ones_like(t_future, dtype=float)]
        for k in range(1, int(max(1, FOURIER_K)) + 1):
            w = 2.0 * np.pi * k * t_future / 12.0
            cols_f.append(np.sin(w))
            cols_f.append(np.cos(w))
        Xf = np.column_stack(cols_f)
        seasonal_future = (Xf @ coef).astype(float)
        df_future["seasonal_fourier"] = seasonal_future
        df_future["temp_deseasonal_fourier"] = df_future["yhat"] - df_future["seasonal_fourier"]
        df_future["anomalia_fourier"] = df_future["temp_deseasonal_fourier"] - mu_ds
    else:
        df_future["seasonal_fourier"] = np.nan
        df_future["temp_deseasonal_fourier"] = np.nan
        df_future["anomalia_fourier"] = np.nan

    # 5. Concatenar Histórico + Futuro
    df_final = pd.concat([df_historical, df_future], ignore_index=True)
    return df_final


def decompose_marcos_holdout_last_n(
    df: pd.DataFrame,
    *,
    col_fecha: str = "fecha",
    col_y: str = "temp_5m",
    holdout_months: int = 12,
    K: int = FOURIER_K,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Modelo base tipo Marcos: tendencia lineal + estacionalidad anual (Fourier mensual).
    Reserva los últimos ``holdout_months`` con observación como holdout (sin ajustar).

    Devuelve un DataFrame alineado a malla mensual ``MS`` entre la primera y última fecha
    con dato, con columnas: ``fecha``, ``observation``, ``fitted``, ``residual``, ``is_holdout``.
    """
    work = df[[col_fecha, col_y]].copy()
    work[col_fecha] = pd.to_datetime(work[col_fecha], errors="coerce")
    work[col_y] = pd.to_numeric(work[col_y], errors="coerce")
    work = work.dropna(subset=[col_fecha]).sort_values(col_fecha)
    obs_dates = sorted(pd.DatetimeIndex(work.loc[work[col_y].notna(), col_fecha]).unique())
    n_obs = len(obs_dates)
    meta_empty: Dict[str, Any] = {"holdout_months": 0, "cutoff_holdout_start": None, "error": "serie vacía"}
    if n_obs < 4:
        return pd.DataFrame(), meta_empty

    min_pts_train = 2 * int(max(1, K)) + 3
    hm = int(max(1, holdout_months))
    hm = min(hm, max(1, n_obs - min_pts_train))
    if hm >= n_obs:
        hm = max(1, n_obs - min_pts_train)
    if hm < 1 or n_obs - hm < min_pts_train:
        return pd.DataFrame(), {**meta_empty, "error": "insuficientes meses para holdout + entrenamiento"}

    cutoff = pd.Timestamp(obs_dates[-hm]).normalize()

    t_min = pd.Timestamp(obs_dates[0]).normalize()
    t_max = pd.Timestamp(obs_dates[-1]).normalize()
    full_idx = pd.date_range(t_min, t_max, freq="MS")
    grid = pd.DataFrame({"fecha": full_idx})
    grid = grid.merge(
        work.rename(columns={col_fecha: "fecha", col_y: "_y_obs"}),
        on="fecha",
        how="left",
    )

    t_mon = _month_index(grid["fecha"])
    t_lin = np.arange(len(grid), dtype=float)
    cols_X = [np.ones(len(grid), dtype=float), t_lin]
    for k in range(1, int(max(1, K)) + 1):
        w = 2.0 * np.pi * k * t_mon / 12.0
        cols_X.append(np.sin(w))
        cols_X.append(np.cos(w))
    X_all = np.column_stack(cols_X)

    train_mask = grid["_y_obs"].notna().to_numpy() & (grid["fecha"].to_numpy() < np.datetime64(cutoff))
    if int(train_mask.sum()) < min_pts_train:
        return pd.DataFrame(), {**meta_empty, "error": "muy pocos puntos de entrenamiento"}

    y_tr = grid.loc[train_mask, "_y_obs"].to_numpy(dtype=float)
    X_tr = X_all[train_mask, :]
    coef, *_ = np.linalg.lstsq(X_tr, y_tr, rcond=None)
    fitted = X_all @ coef

    out = pd.DataFrame(
        {
            "fecha": grid["fecha"],
            "observation": grid["_y_obs"],
            "fitted": fitted.astype(float),
            "residual": grid["_y_obs"].to_numpy(dtype=float) - fitted,
            "is_holdout": (grid["fecha"] >= cutoff).to_numpy(),
        }
    )
    meta_m: Dict[str, Any] = {
        "holdout_months": hm,
        "cutoff_holdout_start": cutoff,
        "fourier_K": int(K),
    }
    return out, meta_m


def marcos_iid_bands_on_residuals(
    rs: pd.Series,
    *,
    cutoff_holdout_start: pd.Timestamp,
    holdout_months: int,
    fechas: pd.Series | None = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Bandas de incertidumbre tipo ATAC (visualización) con error iid gaussiano sobre residuos Marcos.

    - σ = desv. típica de residuos de entrenamiento.
    - Pronóstico de residuo en holdout: media 0 (sin memoria / sin AR).
    - Bandas constantes: ± z · σ en residuo; en la figura se suman a ``fitted``.
    """
    from scipy.stats import norm

    cutoff = pd.Timestamp(cutoff_holdout_start).normalize()
    rs = pd.Series(pd.to_numeric(rs, errors="coerce"), dtype=float).sort_index()
    rs = rs[~rs.index.duplicated(keep="last")]
    rs_clean = rs.dropna()

    z95, z75, z50 = float(norm.ppf(0.975)), float(norm.ppf(0.875)), float(norm.ppf(0.75))

    if rs_clean.size > 1:
        sigma = float(rs_clean.std(ddof=1))
    elif rs_clean.size == 1:
        sigma = 0.0
    else:
        sigma = 1.0
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = 1.0

    meta_a: Dict[str, Any] = {
        "error_model": "marcos_iid_gaussian",
        "residual_sigma": sigma,
        "n_residuals_train": int(rs_clean.size),
    }

    if fechas is not None:
        all_dates = pd.DatetimeIndex(pd.to_datetime(fechas, errors="coerce").dropna().unique()).sort_values()
    else:
        start_d = rs_clean.index.min() if len(rs_clean) else cutoff
        end_d = cutoff + pd.DateOffset(months=max(0, int(holdout_months) - 1))
        all_dates = pd.date_range(pd.Timestamp(start_d).normalize(), end_d, freq="MS")

    holdout_end = cutoff + pd.DateOffset(months=max(0, int(holdout_months) - 1))

    fc_rows: dict[str, list[float]] = {
        "resid_fc_mean": [],
        "resid_fc_lo_95": [],
        "resid_fc_hi_95": [],
        "resid_fc_lo_75": [],
        "resid_fc_hi_75": [],
        "resid_fc_lo_50": [],
        "resid_fc_hi_50": [],
    }
    train_lo_95: list[float] = []
    train_hi_95: list[float] = []

    for ts in all_dates:
        ts = pd.Timestamp(ts).normalize()
        train_lo_95.append(-z95 * sigma)
        train_hi_95.append(z95 * sigma)

        if ts < cutoff or ts > holdout_end:
            for fk in fc_rows:
                fc_rows[fk].append(float("nan"))
            continue

        months_from_cutoff = (ts.year - cutoff.year) * 12 + (ts.month - cutoff.month)
        if months_from_cutoff >= int(holdout_months):
            for fk in fc_rows:
                fc_rows[fk].append(float("nan"))
            continue

        fc_rows["resid_fc_mean"].append(0.0)
        fc_rows["resid_fc_lo_95"].append(-z95 * sigma)
        fc_rows["resid_fc_hi_95"].append(z95 * sigma)
        fc_rows["resid_fc_lo_75"].append(-z75 * sigma)
        fc_rows["resid_fc_hi_75"].append(z75 * sigma)
        fc_rows["resid_fc_lo_50"].append(-z50 * sigma)
        fc_rows["resid_fc_hi_50"].append(z50 * sigma)

    out = pd.DataFrame({"fecha": all_dates, "resid_lo_95": train_lo_95, "resid_hi_95": train_hi_95})
    for k, vals in fc_rows.items():
        out[k] = vals
    return out, meta_a


def atac_holdout_bands_on_residuals(
    rs: pd.Series,
    *,
    cutoff_holdout_start: pd.Timestamp,
    holdout_months: int,
    fechas: pd.Series | None = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Alias histórico: bandas sin AR (Marcos + residuos iid)."""
    return marcos_iid_bands_on_residuals(
        rs,
        cutoff_holdout_start=cutoff_holdout_start,
        holdout_months=holdout_months,
        fechas=fechas,
    )


def main():
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    
    logger.info("Iniciando Previsión Operativa Oceánica (Time Series Forecasting)")
    
    input_file = project_root / "data" / "processed" / "sireno_gijon_ctd_processed.csv"
    output_file = project_root / "data" / "processed" / "sireno_gijon_ctd_forecast.csv"
    
    if not input_file.exists():
        logger.error(f"Archivo de entrada no encontrado: {input_file}")
        logger.error("Asegúrese de que el archivo de entrada procesado existe en data/checked/")
        return
        
    df_processed = pd.read_csv(input_file)
    
    # Validar que existe la variable o usar fallback paramétrico
    target_var = TARGET_VARIABLE 
    if target_var not in df_processed.columns:
        # Fallback a la primera numérica disponible
        num_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
        if num_cols:
            target_var = num_cols[0]
            logger.warning(f"Variable '{TARGET_VARIABLE}' no encontrada. Modelando: {target_var}")
        else:
            logger.error("No se encontraron variables numéricas para pronosticar.")
            return

    if "estacion" in df_processed.columns:
        estaciones = df_processed["estacion"].dropna().unique()
    else:
        df_processed["estacion"] = "global"
        estaciones = ["global"]
    logger.info(f"Target detectado: '{target_var}'. Estaciones a procesar: {len(estaciones)}")
    
    all_forecasts = []
    
    # Modelar cada estación iterativamente
    for st in estaciones:
        logger.info(f"Entrenando modelo Baseline (Statsmodels) para estación: {st}...")
        df_st = df_processed[df_processed['estacion'] == st].copy()
        df_forecast_st = process_station_forecast(df_st, st, target_var)
        
        if not df_forecast_st.empty:
            all_forecasts.append(df_forecast_st)
            
    if not all_forecasts:
        logger.error("No se pudo generar ningún pronóstico válido debido a falta explícita de datos históricos.")
        return
        
    df_final_results = pd.concat(all_forecasts, ignore_index=True)
    
    # Guardar resultados
    df_final_results.to_csv(output_file, index=False)
    
    # Resumen Ejecutivo
    print("\n" + "="*80)
    print(" RESUMEN OPERATIVO: PRONÓSTICO DE SERIES TEMPORALES (MODULO 02) ".center(80, "="))
    print("="*80)
    print(f"Estaciones modeladas      : {len(estaciones)}")
    print(f"Horizonte de proyección   : {FORECAST_HORIZON_YEARS} años")
    print(f"Resolución temporal       : Mensual (malla MS; 12 bins/año)")
    print(f"Intervalo de confianza    : {(1-CONFIDENCE_LEVEL)*100:.0f}%")
    print(f"Variable analizada        : {target_var}")
    print("-" * 80)
    print(f"Arquitectura              : Modular (OceanForecaster base class)")
    print(f"Backend Actual            : ARIMA / Statsmodels StateSpace")
    print(f"Preparación (Scale-out)   : Lista para inyección de Foundation Models (TimeGPT/PatchTST)")
    print("-" * 80)
    print("Qué datos estás viendo en el CSV exportado")
    print(" - `tipo_dato = histórico`: valores observados agregados a media mensual (si hay varios muestreos en un mes, se promedian).")
    print(" - `climatologia_mes`      : media histórica para ese mes (enero..diciembre) usando toda la serie disponible.")
    print(" - `anomalia_mensual`      : `yhat` (mensual) - `climatologia_mes` del mismo mes (también en pronóstico).")
    print(" - `seasonal_fourier`      : componente estacional continuo (K armónicos) ajustado sobre el histórico mensual.")
    print(" - `temp_deseasonal_fourier`: `yhat` - `seasonal_fourier` (señal sin ciclo intra‑anual continuo).")
    print("-" * 80)
    print(f"[OK] Archivo exportado -> {output_file.relative_to(project_root)}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

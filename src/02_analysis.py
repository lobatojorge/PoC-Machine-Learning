"""
Módulo de Análisis y Pronóstico Operativo Oceánico (WGMLEARN)
=============================================================

Este script representa el componente `02_analysis.py` de la arquitectura ODA.
Recoge los datos procesados/saneados por el Agente Inspector y aplica un
modelado predictivo (Time Series Forecasting) para proyectar 5 años hacia
el futuro, calculando intervalos de confianza (95%).

Arquitectura de Clases:
La lógica está encapsulada en `OceanForecaster`, una clase base preparada
para ser extendida en el futuro con Foundation Models de Deep Learning 
(ej. TimeGPT, PatchTST). Actualmente utiliza un modelo estadístico tipo ARIMA
como baseline robusto.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Tuple, Optional, Any
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
# ==========================================

class OceanForecaster:
    """
    Clase modular orientada a objetos para el modelado de series temporales
    oceanográficas. Diseñada con el patrón Strategy para permitir la inyección
    de Foundation Models en el futuro.
    """
    
    def __init__(self, horizon: int = FORECAST_HORIZON_YEARS, alpha: float = CONFIDENCE_LEVEL):
        self.horizon: int = horizon
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
        # Rellenar posibles huecos anuales usando interpolación lineal
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
            # Generar fechas futuras (años)
            future_dates = pd.date_range(
                start=self._last_date + pd.DateOffset(years=1), 
                periods=self.horizon, 
                freq='YE'
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
        
    # Extraer el año y calcular la media.
    # Usamos .groupby() conservando el índice que es el año.
    df_annual = df_station.groupby(df_station['fecha'].dt.year)[target].mean().reset_index()
    df_annual.columns = ['anio', target]
    df_annual['estacion'] = station_name
    
    # Reconstruir datetime a partir del año explícito para el indexado de series temporales
    df_annual['fecha'] = pd.to_datetime(df_annual['anio'].astype(str) + '-06-15')
    
    # 2. Marcar datos históricos
    df_historical = df_annual[['fecha', 'estacion', target]].copy()
    df_historical['yhat_lower'] = df_historical[target]
    df_historical['yhat_upper'] = df_historical[target]
    df_historical.rename(columns={target: 'yhat'}, inplace=True)
    df_historical['tipo_dato'] = 'histórico'
    
    # 3. Modelado Predictivo
    forecaster = OceanForecaster()
    
    # [FEATURE FLAG] En el futuro:
    # forecaster = DeepOceanForecaster(foundation_model="TimeGPT")
    
    forecaster.fit(df_annual, target)
    df_future = forecaster.predict()
    
    # 4. Formatear y alinear DataFrame del pronóstico
    df_future['estacion'] = station_name
    df_future.rename(columns={
        'forecast_mean': 'yhat',
        'forecast_lower': 'yhat_lower',
        'forecast_upper': 'yhat_upper'
    }, inplace=True)
    df_future['tipo_dato'] = 'pronóstico'
    
    # 5. Concatenar Histórico + Futuro
    df_final = pd.concat([df_historical, df_future], ignore_index=True)
    return df_final


def main():
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    
    logger.info("Iniciando Previsión Operativa Oceánica (Time Series Forecasting)")
    
    input_file = project_root / "data" / "processed" / "sireno_gijon_ctd_processed.csv"
    output_file = project_root / "data" / "processed" / "sireno_gijon_ctd_forecast.csv"
    
    if not input_file.exists():
        logger.error(f"Archivo de entrada no encontrado: {input_file}")
        logger.error("Asegúrese de ejecutar primero '01_agent_inspector.py'")
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
    print(f"Intervalo de confianza    : {(1-CONFIDENCE_LEVEL)*100:.0f}%")
    print(f"Variable analizada        : {target_var}")
    print("-" * 80)
    print(f"Arquitectura              : Modular (OceanForecaster base class)")
    print(f"Backend Actual            : ARIMA / Statsmodels StateSpace")
    print(f"Preparación (Scale-out)   : Lista para inyección de Foundation Models (TimeGPT/PatchTST)")
    print("-" * 80)
    print(f"[OK] Archivo exportado -> {output_file.relative_to(project_root)}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

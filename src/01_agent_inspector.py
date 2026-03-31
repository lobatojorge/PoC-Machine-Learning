"""
Módulo de Data Observability y Detección de Anomalías (WGMLEARN)
=================================================================

Este script actúa como el agente inspector del pipeline de datos.
Utiliza Machine Learning no supervisado (Isolation Forest de scikit-learn)
para identificar anomalías multivariantes, como por ejemplo combinaciones
inusuales termo-halinas para una época del año concreta que carecen de
sentido físico o biológico.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    IsolationForest = None  # type: ignore[assignment]
    SKLEARN_AVAILABLE = False

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN DE HIPERPARÁMETROS
# ==========================================
CONTAMINATION_RATE = 0.05  # Proporción esperada de valores atípicos (5%)
RANDOM_STATE = 42          # Semilla para reproducibilidad de los árboles
N_ESTIMATORS = 100         # Número de estimadores (árboles) en el bosque
# ==========================================

def setup_directories(base_path: Path) -> dict:
    """
    Verifica y crea la estructura de directorios necesaria para los datos 
    procesados y los reportes forenses.
    
    Args:
        base_path (Path): Ruta raíz del proyecto.
        
    Returns:
        dict: Diccionario con las rutas a los directorios creados.
    """
    dir_paths = {
        "processed": base_path / "data" / "processed",
        "quarantine": base_path / "data" / "quarantine",
        "reports": base_path / "outputs" / "reports",
    }
    
    for name, path in dir_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio verificado/creado: {path.relative_to(base_path) if base_path in path.parents else path}")
        
    return dir_paths

def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae las características numéricas para el modelo de ML de forma flexible.

    Selecciona automáticamente todas las columnas con tipo numérico (np.number).
    Imputa nulos con la mediana para que Isolation Forest no falle.
    """
    # 1. Seleccionar solo columnas numéricas (sin depender de nombres rígidos)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if len(numeric_cols) < 2:
        return pd.DataFrame()  # Isolation Forest requiere al menos 2 variables

    x_features = df[numeric_cols].copy()

    # 2. Tratamiento de nulos: imputar con la mediana (Isolation Forest no acepta NaNs)
    x_features = x_features.apply(pd.to_numeric, errors="coerce")
    x_features = x_features.fillna(x_features.median())

    # Si alguna columna era toda NaN, rellenar con 0 como último recurso
    x_features = x_features.fillna(0)

    return x_features

def detect_anomalies(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Aplica Isolation Forest y devuelve datos sanos, sospechosos y contexto estadístico.

    Returns
    -------
    df_sano : pd.DataFrame
        Filas clasificadas como normales (inliers).
    df_sospechoso : pd.DataFrame
        Filas marcadas como anomalía (-1) por Isolation Forest.
    contexto_estadistico : dict
        Medianas y desviaciones estándar de las características analizadas
        (para evaluación cognitiva / LLM).
    """
    x_features = extract_features(df)
    df_result = df.copy()

    if x_features.empty:
        logger.warning(
            "Características insuficientes para detectar anomalías multivariantes."
        )
        df_result["is_anomaly"] = False
        df_result["anomaly_score"] = 0.0
        return df_result, pd.DataFrame(), {}

    # Contexto estadístico del bloque analizado (medianas y std por variable)
    medians = x_features.median().to_dict()
    stds = x_features.std().replace({0: np.nan}).to_dict()
    contexto_estadistico = {
        "medianas": medians,
        "desviaciones_estandar": stds,
    }

    if SKLEARN_AVAILABLE:
        logger.info(
            "Entrenando modelo Isolation Forest con contaminación del %.1f%%...",
            CONTAMINATION_RATE * 100,
        )

        model = IsolationForest(
            n_estimators=N_ESTIMATORS,
            contamination=CONTAMINATION_RATE,
            random_state=RANDOM_STATE,
        )
        preds = model.fit_predict(x_features)
        scores = model.decision_function(x_features)
        df_result["is_anomaly"] = preds == -1
        df_result["anomaly_score"] = scores
    else:
        logger.warning(
            "scikit-learn no está disponible. Usando fallback estadístico robusto."
        )
        med_series = x_features.median()
        std_series = x_features.std().replace(0, np.nan).fillna(1.0)

        # Distancia normalizada al centro robusto (mediana).
        z = (x_features - med_series) / std_series
        dist = np.sqrt((z**2).sum(axis=1))
        threshold = dist.quantile(1 - CONTAMINATION_RATE)

        df_result["is_anomaly"] = dist > threshold
        # Signo negativo para mantener semántica: más negativo = más anómalo.
        df_result["anomaly_score"] = -dist

    df_sano = df_result[~df_result["is_anomaly"]].copy()
    df_sospechoso = df_result[df_result["is_anomaly"]].copy()

    return df_sano, df_sospechoso, contexto_estadistico


async def evaluacion_cognitiva_llm(
    df_sospechoso: pd.DataFrame,
    contexto: dict[str, Any],
) -> pd.DataFrame:
    """
    Placeholder de evaluación cognitiva por LLM.

    Por ahora solo añade la columna veredicto_agente indicando que
    los registros quedan pendientes de validación.
    """
    out = df_sospechoso.copy()
    out["veredicto_agente"] = "Pendiente de validación LLM"
    return out

def main():
    """
    Función principal que orquesta el agente inspector.
    Escanea data/interim y procesa dinámicamente todos los CSV encontrados.
    """
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent

    logger.info("Iniciando Agente Inspector Multivariante (ML Oceánico)")
    if not SKLEARN_AVAILABLE:
        logger.warning(
            "Dependencia opcional 'scikit-learn' no encontrada; se aplicará fallback estadístico."
        )

    # FASE 0: DIRECTORIOS
    dirs = setup_directories(project_root)
    interim_dir = project_root / "data" / "interim"
    interim_dir.mkdir(parents=True, exist_ok=True)

    # Búsqueda enfocada al flujo Sireno Gijón
    archivos_interim = sorted(interim_dir.glob("sireno_gijon_ctd_interim.csv"))

    if not archivos_interim:
        logger.info(
            "No hay archivos CSV en data/interim. No hay datos nuevos que procesar."
        )
        sys.exit(0)

    logger.info(f"Se encontraron {len(archivos_interim)} archivo(s) en data/interim.")

    quarantine_dir = dirs["quarantine"]
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    total_records = 0
    total_sospechosos = 0

    # BUCLE DE PROCESAMIENTO: un archivo interim -> processed + quarantine
    for input_file in archivos_interim:
        stem = input_file.stem
        out_stem = stem.replace("_interim", "_processed") + ".csv"
        processed_file = dirs["processed"] / out_stem
        quarantine_file = quarantine_dir / f"{stem}_quarantine.csv"

        logger.info(f"Procesando: {input_file.name} -> {out_stem}")

        try:
            df = pd.read_csv(input_file, sep=None, engine="python")
        except Exception as e:
            logger.error(f"Error leyendo {input_file.name}: {e}")
            continue

        # Rescate de año para robustez del pipeline (si se perdiera en pasos previos)
        lower_map = {str(c).lower().strip(): c for c in df.columns}
        has_year = any(c in lower_map for c in ("ano", "año", "year", "anio", "yy"))
        if not has_year:
            for col_name in ("estacion", "acronimo"):
                if col_name in lower_map:
                    col_real = lower_map[col_name]
                    extracted = (
                        df[col_real]
                        .astype(str)
                        .str.extract(r"((?:19|20)\d{2})")[0]
                    )
                    if extracted.notna().any():
                        df["ano"] = pd.to_numeric(extracted, errors="coerce")
                        logger.info(
                            "Columna 'ano' reconstruida dinámicamente desde '%s'.",
                            col_real,
                        )
                        break

        n_rows = len(df)
        total_records += n_rows

        if n_rows < 10:
            logger.warning(
                f"  Dataset muy pequeño ({n_rows} filas). Se procesa igualmente."
            )

        # FASE 1: DETECCIÓN (salida híbrida: sano, sospechoso, contexto)
        df_sano, df_sospechoso, contexto_estadistico = detect_anomalies(df)

        # FASE 2: VOLCADO DATOS SANOS A PROCESSED
        df_sano.to_csv(processed_file, index=False)
        logger.info(
            f"  Datos sanos guardados en {processed_file.relative_to(project_root)}"
        )

        # FASE 3: EVALUACIÓN COGNITIVA (placeholder) Y CUARENTENA
        if not df_sospechoso.empty:
            df_cuarentena = asyncio.run(
                evaluacion_cognitiva_llm(df_sospechoso, contexto_estadistico)
            )
            df_cuarentena.to_csv(quarantine_file, index=False)
            total_sospechosos += len(df_sospechoso)
            logger.warning(
                f"  Registros sospechosos en cuarentena: {quarantine_file.relative_to(project_root)} ({len(df_sospechoso)} filas)"
            )
        else:
            logger.info("  Sin registros sospechosos para este archivo.")

    # RESUMEN EJECUTIVO
    print("\n" + "=" * 80)
    print(
        " RESUMEN EJECUTIVO: INSPECTOR (OBSERVABILIDAD COGNITIVA) ".center(80, "=")
    )
    print("=" * 80)
    print(f"Archivos procesados         : {len(archivos_interim)}")
    print(f"Total registros analizados : {total_records}")
    print(f"Modelo empleado            : Isolation Forest (scikit-learn)")
    print(f"Tasa de contaminación base : {CONTAMINATION_RATE * 100:.1f}%")
    print("-" * 80)
    print(f"[OK] Datos sanos             : data/processed/")
    print(
        f"[!!] En cuarentena (LLM)      : {total_sospechosos} ({(total_sospechosos/total_records)*100 if total_records > 0 else 0:.1f}%) -> data/quarantine/"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

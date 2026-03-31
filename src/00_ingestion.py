"""
Módulo de Ingestión de Datos Oceanográficos (Radiales CTD)
===========================================================

Este script actúa como el primer eslabón del pipeline de datos.
Su objetivo es ingerir los datos reales desde ExcelSirenoGijon.xls,
decodificar el año y el mes desde la columna ACRONIMO, filtrar la
estación 4 (sin cobertura suficiente a 5 m) y generar un CSV limpio
listo para la visualización.

Codificación del acrónimo
--------------------------
    RADGIJ{MM}{AA}
    RADGIJ0103  → mes=1 (enero), año=2003
    RADGIJ0902  → mes=9 (septiembre), año=2002

Fases del script:
1. Extracción  — lectura multi-hoja del Excel.
2. Decodificación — ACRONIMO → columnas `mes` y `anio`.
3. Filtrado — excluir estación 4.
4. Limpieza estructural — cabeceras minúsculas, sin tildes.
5. Carga — guarda `data/processed/sireno_gijon_clean.csv`.
"""

import pandas as pd
from pathlib import Path
import re
import unicodedata
import logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades de limpieza
# ---------------------------------------------------------------------------

def clean_string(text: str) -> str:
    """
    Limpia un string: elimina tildes, convierte a minúsculas y
    sustituye espacios por barras bajas.
    """
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def standardize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Estandariza los nombres de las columnas del DataFrame."""
    df.columns = pd.Index([clean_string(col) for col in df.columns])
    return df


# ---------------------------------------------------------------------------
# Decodificación del acrónimo
# ---------------------------------------------------------------------------

def decode_acronimo(acronimo_series: pd.Series) -> pd.DataFrame:
    """
    Decodifica la columna ACRONIMO (p.ej. 'RADGIJ0103') en dos columnas:

        mes  : int (1-12)
        anio : int (e.g. 2003)

    Formato: RADGIJ{MM}{AA}
        MM = mes con cero inicial (01-12)
        AA = año en 2 dígitos (00-99 → 2000-2099)

    Registros con acrónimo irrecuperable reciben NaN en ambas columnas.
    """
    # Extraer los últimos 4 caracteres numéricos del acrónimo
    # Patrón esperado: cadena cualquiera seguida de exactamente 4 dígitos al final
    extracted = acronimo_series.astype(str).str.extract(r"(\d{2})(\d{2})$")
    extracted.columns = pd.Index(["mm_str", "aa_str"])

    mes = pd.to_numeric(extracted["mm_str"], errors="coerce").astype("Int64")
    anio_2d = pd.to_numeric(extracted["aa_str"], errors="coerce").astype("Int64")

    # Convertir año de 2 dígitos a 4 dígitos (asumimos siglo XXI: 00-99 → 2000-2099)
    anio = anio_2d + 2000

    return pd.DataFrame({"mes": mes, "anio": anio})


# ---------------------------------------------------------------------------
# Ingesta principal
# ---------------------------------------------------------------------------

def ingest_sireno_ctd(filepath: Path | str) -> pd.DataFrame:
    """
    Ingesta y limpieza del Excel histórico de Sireno Gijón (Radiales CTD).

    Pasos:
    1. Leer todas las hojas cuyo nombre contenga 'RadGIJ' o 'CTD'.
    2. Concatenar en un DataFrame maestro.
    3. Estandarizar cabeceras (minúsculas, sin tildes).
    4. Decodificar ACRONIMO → columnas `mes` y `anio`.
    5. Excluir estación 4 (cobertura insuficiente a 5 m).
    6. Exportar a `data/processed/sireno_gijon_clean.csv`.

    Returns el DataFrame limpio.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de datos Sireno CTD en: {filepath}"
        )

    logger.info(f"Ingestando Excel Sireno CTD desde: {filepath.name}")

    try:
        xl = pd.ExcelFile(filepath)
    except ImportError as exc:
        raise ImportError(
            "No se pudo leer el Excel .xls. Instala 'xlrd' para habilitar "
            "la lectura de archivos legacy de Excel."
        ) from exc

    sheet_names = xl.sheet_names
    logger.info(f"Pestañas detectadas: {sheet_names}")

    # --- Fase 1: Leer hojas relevantes ---
    frames: list[pd.DataFrame] = []
    for sheet in sheet_names:
        sheet_lower = str(sheet).lower()
        if "radgij" in sheet_lower or "ctd" in sheet_lower:
            logger.info(f"  -> Leyendo hoja: {sheet!r}")
            df_sheet = xl.parse(str(sheet))
            frames.append(df_sheet)
        else:
            logger.info(f"  -> Ignorando hoja: {sheet!r}")

    if not frames:
        raise ValueError(
            "No se encontró ninguna pestaña relevante (RadGIJ / CTD) "
            f"en el archivo: {filepath}"
        )

    # --- Fase 2: Concatenar ---
    df_master = pd.concat(frames, ignore_index=True)
    logger.info(f"DataFrame maestro: {df_master.shape[0]} filas × {df_master.shape[1]} columnas")

    # --- Fase 3: Estandarizar cabeceras ---
    df_master = standardize_headers(df_master)
    logger.info(f"Cabeceras limpias: {df_master.columns.tolist()}")

    # --- Fase 4: Decodificar ACRONIMO → mes + anio ---
    col_acron = next((c for c in df_master.columns if "acron" in c), None)
    if col_acron is None:
        raise ValueError(
            "No se encontró la columna ACRONIMO en el DataFrame maestro. "
            f"Columnas disponibles: {df_master.columns.tolist()}"
        )

    decoded = decode_acronimo(df_master[col_acron])
    df_master["mes"] = decoded["mes"]
    df_master["anio"] = decoded["anio"]

    n_bad = df_master[["mes", "anio"]].isna().any(axis=1).sum()
    if n_bad > 0:
        logger.warning(
            f"{n_bad} registros con acrónimo no decodificable. "
            "Se excluirán del CSV final."
        )
    df_master = df_master.dropna(subset=["mes", "anio"])
    df_master["mes"] = df_master["mes"].astype(int)
    df_master["anio"] = df_master["anio"].astype(int)

    logger.info(
        f"Rango temporal: {df_master['anio'].min()}–{df_master['anio'].max()}, "
        f"meses disponibles: {sorted(df_master['mes'].unique())}"
    )

    # --- Fase 5: Excluir estación 4 ---
    col_est = next((c for c in df_master.columns if "estac" in c), None)
    if col_est:
        antes = len(df_master)
        df_master = df_master[df_master[col_est] != 4].copy()
        # Renombrar a nombre limpio
        df_master = df_master.rename(columns={col_est: "estacion"})
        logger.info(
            f"Estación 4 excluida: {antes} → {len(df_master)} filas. "
            f"Estaciones restantes: {sorted(df_master['estacion'].unique())}"
        )
    else:
        logger.warning("No se encontró columna de estación. No se aplicó filtro de estación 4.")

    # --- Fase 6: Guardar CSV limpio ---
    project_root = Path(__file__).resolve().parent.parent
    out_path = project_root / "data" / "processed" / "sireno_gijon_clean.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_master.to_csv(out_path, index=False)
    logger.info(f"CSV limpio guardado en: {out_path}")

    return df_master


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def setup_directories(base_path: Path) -> dict:
    """Verifica y crea la estructura de directorios."""
    dir_paths = {
        "raw": base_path / "data" / "raw",
        "processed": base_path / "data" / "processed",
    }
    for path in dir_paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return dir_paths


def main() -> None:
    """Punto de entrada: ejecuta la ingesta Sireno CTD y muestra un resumen."""
    project_root = Path(__file__).resolve().parent.parent
    logger.info("Iniciando Pipeline de Ingestión (Sireno CTD Gijón)")
    setup_directories(project_root)

    raw_file_path = project_root / "data" / "raw" / "ExcelSirenoGijon.xls"
    if not raw_file_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de datos reales en:\n{raw_file_path}\n"
            "Por favor, deposite el Excel allí antes de ejecutar el pipeline."
        )

    df = ingest_sireno_ctd(raw_file_path)

    print("\n" + "=" * 80)
    print(" INGESTA SIRENO CTD (GIJÓN) COMPLETADA ".center(80, "="))
    print("=" * 80)
    print(f"Directorio raíz     : {project_root}")
    print(f"Fuente de datos     : {raw_file_path.name}")
    print(f"Total de registros  : {len(df):,}")
    print(f"Total de columnas   : {len(df.columns)}")
    print(f"Cobertura temporal  : {df['anio'].min()}–{df['anio'].max()}")
    print(f"Meses disponibles   : {sorted(df['mes'].unique())}")
    if "estacion" in df.columns:
        print(f"Estaciones (sin 4)  : {sorted(df['estacion'].unique())}")
    print("-" * 80)
    print("Columnas finales:")
    for col in df.columns:
        print(f"  - {col}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

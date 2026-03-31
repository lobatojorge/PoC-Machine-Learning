"""
================================================================================
00_data_scout.py — Agente de Reconocimiento de Datasets Crudos
================================================================================
Rol    : Data Engineer / Arquitecto de Datos Oceánicos
Misión : Analizar la estructura de un dataset crudo SIN modificarlo y exportar
         un informe de auditoría a outputs/reports/.

Uso    : python src/00_data_scout.py
================================================================================
"""

from __future__ import annotations

import sys
import io
from datetime import datetime
from pathlib import Path

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE RUTAS  (todo relativo al raíz del proyecto)
# ──────────────────────────────────────────────────────────────────────────────

# El script vive en src/, así que el raíz del proyecto es su carpeta padre.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR     = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

# Flujo actual: reconocimiento de datasets en data/raw con foco en Sireno Gijón
REPORT_NAME = "recon_data_raw.txt"
DATA_DICTIONARY_PATH = PROJECT_ROOT / "docs" / "data_dictionary.yaml"


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ──────────────────────────────────────────────────────────────────────────────


def load_data_dictionary(path: Path) -> dict[str, dict[str, str]] | None:
    """
    Carga el glosario de variables desde docs/data_dictionary.yaml.
    Estructura: { nombre_archivo: { nombre_columna: descripcion } }.
    Si el archivo no existe, está mal formado o falta PyYAML, devuelve None
    (el scout seguirá funcionando sin descripciones).
    """
    if not path.exists():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def _glossary_description_for_column(
    file_glossary: dict[str, str], column_name: str
) -> str | None:
    """Busca descripción para una columna (coincidencia case-insensitive)."""
    col_norm = str(column_name).strip().lower()
    for k, v in (file_glossary or {}).items():
        if str(k).strip().lower() == col_norm and v:
            return v
    return None


def _columns_without_description(
    file_glossary: dict[str, str], column_names: list
) -> list[str]:
    """Columnas del DataFrame que no tienen entrada en el glosario del archivo."""
    if not file_glossary:
        return list(column_names)
    result = []
    for c in column_names:
        if _glossary_description_for_column(file_glossary, c) is None:
            result.append(str(c))
    return result

def detect_file(directory: Path, stem: str) -> Path:
    """
    Busca el archivo con el *stem* dado en *directory* probando
    las extensiones .xlsx, .xls y .csv (en ese orden de preferencia).

    Lanza FileNotFoundError si no encuentra ninguna variante.
    """
    for ext in (".xlsx", ".xls", ".csv"):
        candidate = directory / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No se encontró ningún archivo con nombre '{stem}' "
        f"(.xlsx / .xls / .csv) en:\n  {directory}"
    )


def load_dataset(filepath: Path) -> tuple[pd.DataFrame, list[str] | None]:
    """
    Carga el dataset en un DataFrame sin modificar el original.

    Devuelve:
        df          — DataFrame con los datos de la primera hoja/tabla.
        sheet_names — Lista de pestañas si es Excel; None si es CSV.

    Lanza:
        ValueError  si la extensión no es reconocida.
        Exception   si el archivo está corrupto o tiene formato inesperado.
    """
    ext = filepath.suffix.lower()

    if ext in (".xlsx", ".xls"):
        xl = pd.ExcelFile(filepath)
        sheet_names: list[str] = xl.sheet_names
        df = xl.parse(sheet_names[0])        # analiza sólo la primera hoja
        return df, sheet_names

    elif ext == ".csv":
        df = pd.read_csv(filepath)
        return df, None

    else:
        raise ValueError(f"Extensión no soportada: '{ext}'")


def build_report(
    filepath: Path,
    df: pd.DataFrame,
    sheet_names: list[str] | None,
    glossary: dict[str, dict[str, str]] | None = None,
) -> str:
    """
    Construye el texto completo del informe de reconocimiento.
    Si glossary está presente, enriquece con descripciones y añade sección
    "Columnas sin descripción".
    """
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep    = "═" * 72
    thin   = "─" * 72
    n_rows, n_cols = df.shape

    lines: list[str] = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    lines += [
        sep,
        "  INFORME DE RECONOCIMIENTO — DATA SCOUT  v1.0",
        f"  Proyecto  : Antigravity / IEO",
        f"  Fecha     : {now}",
        sep,
        "",
        f"  Archivo   : {filepath.name}",
        f"  Ruta      : {filepath.relative_to(PROJECT_ROOT)}",
        f"  Tamaño    : {filepath.stat().st_size / 1024:.2f} KB",
        "",
    ]

    # ── Pestañas (sólo Excel) ─────────────────────────────────────────────────
    if sheet_names is not None:
        lines.append(thin)
        lines.append("  PESTAÑAS DETECTADAS (Excel)")
        lines.append(thin)
        for i, name in enumerate(sheet_names, start=1):
            marker = " ◄ analizada" if i == 1 else ""
            lines.append(f"    [{i}] {name}{marker}")
        lines.append("")

    # ── Dimensiones ───────────────────────────────────────────────────────────
    lines += [
        thin,
        "  DIMENSIONES",
        thin,
        f"    Filas     : {n_rows:,}",
        f"    Columnas  : {n_cols:,}",
        "",
    ]

    # ── Detalle por columna ───────────────────────────────────────────────────
    file_glossary = (glossary or {}).get(filepath.name) or {}
    lines += [
        thin,
        "  DETALLE DE COLUMNAS",
        thin,
        f"  {'#':<5} {'NOMBRE':<35} {'DTYPE':<15} {'NULOS':>8}  {'% NULO':>8}",
        f"  {'─'*5} {'─'*35} {'─'*15} {'─'*8}  {'─'*8}",
    ]

    null_counts = df.isnull().sum()
    for idx, col in enumerate(df.columns, start=1):
        dtype   = str(df[col].dtype)
        n_null  = null_counts[col]
        pct     = (n_null / n_rows * 100) if n_rows > 0 else 0.0
        lines.append(
            f"  {idx:<5} {str(col):<35} {dtype:<15} {n_null:>8,}  {pct:>7.2f}%"
        )
        desc = _glossary_description_for_column(file_glossary, col)
        if desc:
            lines.append(f"       Descripción : {desc}")

    lines.append("")

    # ── Columnas sin descripción (si hay glosario cargado) ─────────────────────
    if glossary is not None:
        sin_desc = _columns_without_description(file_glossary, list(df.columns))
        lines += [
            thin,
            "  COLUMNAS SIN DESCRIPCIÓN (preguntar al creador de los datos)",
            thin,
        ]
        if sin_desc:
            for c in sin_desc:
                lines.append(f"    - {c}")
        else:
            lines.append("    (ninguna)")
        lines.append("")

    # ── Resumen de calidad ────────────────────────────────────────────────────
    total_cells   = n_rows * n_cols
    total_nulls   = int(null_counts.sum())
    pct_complete  = (1 - total_nulls / total_cells) * 100 if total_cells > 0 else 0.0
    cols_with_nulls = int((null_counts > 0).sum())

    lines += [
        thin,
        "  RESUMEN DE CALIDAD",
        thin,
        f"    Celdas totales        : {total_cells:,}",
        f"    Valores nulos totales : {total_nulls:,}",
        f"    Columnas con nulos    : {cols_with_nulls} / {n_cols}",
        f"    Completitud           : {pct_complete:.2f}%",
        "",
        sep,
        "  FIN DEL INFORME",
        sep,
    ]

    return "\n".join(lines)


def scan_raw_files(directory: Path) -> list[Path]:
    """
    Devuelve la lista de archivos a analizar en `data/raw/`.

    Extensiones soportadas (case-insensitive):
    - .csv, .tsv, .txt
    - .xlsx, .xls
    """
    exts = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
    files: list[Path] = []

    if not directory.exists():
        return files

    for p in directory.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)

    return sorted(files)


def robust_read_csv(filepath: Path) -> tuple[pd.DataFrame, str | None, str | None, str | None]:
    """
    Intenta leer un archivo de texto (CSV/TSV/TXT) probando distintas
    combinaciones de encoding y separador para ser robusto frente a
    CSVs generados por Excel en español.

    Estrategia:
    - Encodings: utf-8, latin1, cp1252.
    - Separadores: ',', ';', '\\t'.

    Devuelve:
        df         — DataFrame (puede ser vacío si todas las combinaciones fallan).
        encoding   — Encoding que funcionó, o None.
        sep        — Separador que funcionó, o None.
        last_error — Texto del último error si todas las combinaciones fallan, o None.
    """
    encodings = ["utf-8", "latin1", "cp1252"]
    seps = [",", ";", "\t"]

    last_error: str | None = None

    for enc in encodings:
        for sep in seps:
            try:
                df = pd.read_csv(filepath, encoding=enc, sep=sep)
                return df, enc, repr(sep), None
            except Exception as exc:  # pragma: no cover - logging defensivo
                last_error = f"{type(exc).__name__}: {exc}"
                continue

    # Si llegamos aquí, todas las combinaciones han fallado
    return pd.DataFrame(), None, None, last_error


def load_dataset_safe(
    filepath: Path,
) -> tuple[pd.DataFrame, list[str] | None, dict[str, str | None]]:
    """
    Variante robusta de carga de datasets que:
    - Soporta .csv / .tsv / .txt con detección de encoding y separador.
    - Soporta .xlsx / .xls capturando errores de engine (openpyxl/xlrd).
    - Nunca lanza excepción; devuelve df vacío y metadatos con el error.
    """
    ext = filepath.suffix.lower()
    meta: dict[str, str | None] = {
        "encoding": None,
        "sep": None,
        "engine": None,
        "error": None,
    }

    # Texto plano (CSV/TSV/TXT) con lectura robusta
    if ext in (".csv", ".tsv", ".txt"):
        df, enc, sep, last_error = robust_read_csv(filepath)
        meta["encoding"] = enc
        meta["sep"] = sep
        meta["engine"] = "pandas.read_csv"
        meta["error"] = last_error
        return df, None, meta

    # Ficheros Excel
    if ext in (".xlsx", ".xls"):
        try:
            xl = pd.ExcelFile(filepath)
            sheet_names: list[str] = xl.sheet_names
            df = xl.parse(sheet_names[0])  # analiza sólo la primera hoja
            engine = getattr(xl, "engine", None)
            meta["engine"] = str(engine) if engine is not None else "excel"
            return df, sheet_names, meta
        except ImportError as exc:
            meta["error"] = (
                f"ImportError al leer Excel (¿falta openpyxl/xlrd?): {exc}"
            )
            return pd.DataFrame(), None, meta
        except Exception as exc:
            meta["error"] = f"{type(exc).__name__}: {exc}"
            return pd.DataFrame(), None, meta

    # Extensión no soportada
    meta["error"] = f"Extensión no soportada: '{ext}'"
    return pd.DataFrame(), None, meta


def build_report_with_meta(
    filepath: Path,
    df: pd.DataFrame,
    sheet_names: list[str] | None,
    meta: dict[str, str | None],
    glossary: dict[str, dict[str, str]] | None = None,
) -> str:
    """
    Envuelve `build_report` añadiendo un bloque explícito de parámetros
    de lectura (encoding, separador, engine, errores).
    """
    core = build_report(filepath, df, sheet_names, glossary)

    meta_block = [
        "",
        "  PARÁMETROS DE LECTURA",
        "  ─────────────────────────────────────────────────────────────",
        f"    Encoding usado : {meta.get('encoding') or '-'}",
        f"    Separador usado: {meta.get('sep') or '-'}",
        f"    Engine         : {meta.get('engine') or '-'}",
        f"    Último error   : {meta.get('error') or '-'}",
        "",
    ]

    return core + "\n" + "\n".join(meta_block)

def save_report(report_text: str, output_path: Path) -> None:
    """Guarda el informe en disco, creando el directorio si no existe."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # Forzar UTF-8 en stdout para mostrar correctamente los caracteres del
    # informe en terminales Windows que usan CP1252 como encoding por defecto.
    # open() sobre el buffer subyacente es más type-safe que .reconfigure().
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,  # type: ignore[union-attr]
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
    except AttributeError:
        pass  # Entornos sin .buffer (p.ej. IDLE, notebooks) — se ignora.

    print("\n[*] Iniciando agente de reconocimiento...\n")

    # 0 · Cargar glosario de variables (opcional) ---------------------------
    glossary = load_data_dictionary(DATA_DICTIONARY_PATH)
    if glossary:
        print("[OK] Glosario de variables cargado (docs/data_dictionary.yaml)")
    else:
        print("[--] Sin glosario; informe sin descripciones semánticas.")

    # 1 · Escanear archivos en data/raw --------------------------------------
    files = scan_raw_files(RAW_DIR)
    if not files:
        print(f"[!!] No se encontraron archivos soportados en {RAW_DIR}")
        sys.exit(1)

    print(f"[OK] Archivos detectados ({len(files)}) en data/raw/:")
    for p in files:
        print(f"     - {p.name}")

    all_reports: list[str] = []

    # 2 · Procesar cada archivo de forma independiente (sin fugas de estado) -
    for filepath in files:
        print(f"\n[>] Analizando archivo: {filepath.name}")

        # Inicializar variables por archivo para evitar fugas de estado
        df: pd.DataFrame = pd.DataFrame()
        sheet_names: list[str] | None = None
        meta: dict[str, str | None] = {}

        # 2.1 · Carga robusta
        df, sheet_names, meta = load_dataset_safe(filepath)

        if meta.get("error") and df.empty:
            # Registrar igualmente en el informe aunque no se haya podido leer
            print(f"    [!!] Error de lectura: {meta['error']}")

        else:
            print(
                f"    [OK] Dataset cargado: {df.shape[0]:,} filas x {df.shape[1]:,} columnas"
            )
            if sheet_names:
                print(f"         Pestañas Excel: {sheet_names}")

        # 2.2 · Construir informe para este archivo
        try:
            report_text = build_report_with_meta(
                filepath, df, sheet_names, meta, glossary
            )
            all_reports.append(report_text)
        except Exception as exc:
            print(
                f"[!!] ERROR al generar el informe para '{filepath.name}': "
                f"{type(exc).__name__}: {exc}"
            )
            continue

    # 3 · Imprimir por consola -----------------------------------------------
    final_report = "\n\n".join(all_reports)
    print()
    print(final_report)

    # 4 · Exportar a disco ---------------------------------------------------
    try:
        output_path = REPORTS_DIR / REPORT_NAME
        save_report(final_report, output_path)
        rel_path = output_path.relative_to(PROJECT_ROOT)
        print(f"\n[OK] Informe exportado : {rel_path}\n")
    except Exception as exc:
        print(f"[!!] ERROR al guardar el informe: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

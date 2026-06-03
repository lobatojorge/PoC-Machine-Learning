"""
Utilidades compartidas para cabeceras SeaBird ``.cnv``.

Los ficheros IEO suelen ser SBE 19/25 con líneas ``# name N = var: descripción`` donde
``var`` puede contener ``/`` (p.ej. ``c0S/m``). El patrón antiguo ``\\w+`` fallaba y
dejaba columnas fuera, lo que vaciaba la lista y mandaba todo a cuarentena.

También muchos .cnv **no** traen ``timeJ`` en columnas: solo ``# start_time =`` en
cabecera; la puerta debe aceptar ese caso.

El año en ``# start_time`` suele ser erróneo (calibración SBE). La fuente de verdad
preferida es la carpeta ``YYYY/`` o el sufijo del nombre de fichero (``apr94``, ``gnov105``).
"""

from __future__ import annotations

import re
from pathlib import Path

# ``# name 0 = prSM: ...`` o ``# name 2 = c0S/m: ...``
CNV_NAME_LINE_RE = re.compile(r"^#\s+name\s+\d+\s*=\s*(.+?)\s*:\s*", re.IGNORECASE)

# ``# start_time = Jul 17 2001 11:54:25`` (mes abreviado inglés o español)
CNV_START_TIME_RE = re.compile(
    r"^#\s*start_time\s*=\s*"
    r"(\w+)\s+(\d+)\s+(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})",
    re.IGNORECASE,
)

# Meses en cabecera SBE (inglés + español frecuente en nombres de fichero IEO)
_MONTHS: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "ene": 1,
    "abr": 4,
    "ago": 8,
    "dic": 12,
}

# ``** Station:    6`` o ``** Station: C3`` o ``** Numero de estacion: 3``
CNV_STATION_LINE_RE = re.compile(
    r"^\*+\s*(?:Station|Estaci[oó]n|N[uú]mero\s+de\s+estaci[oó]n):\s*(.+)",
    re.IGNORECASE,
)

_STATION_FOLDER_RE = re.compile(r"[Ss]t[\.\s_]?(\d+)", re.IGNORECASE)
_STATION_FILE_RE = re.compile(r"[Ss]t[Cc\s_]?(\d+)", re.IGNORECASE)

_MONTH_TOKEN = (
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|ene|abr|ago|dic"
)

# ``apr94``, ``aug93`` al inicio; ``gnov105`` → ``nov`` + ``05`` al final (prefijo radial ``g``)
_FILENAME_MONTH_YEAR_SUFFIX_RE = re.compile(
    rf"(?:{_MONTH_TOKEN})(\d{{2}})$",
    re.IGNORECASE,
)

# Sufijo solo numérico si no hubo mes: ``foo99.cnv`` raro
_FILENAME_TAIL_YEAR_RE = re.compile(r"(\d{2})$")


def _two_digit_year_to_full(y2: int) -> int:
    """Convención oceanografía histórica: 80–99 → 19xx, 00–79 → 20xx."""
    return y2 + 1900 if y2 >= 80 else y2 + 2000


def year_from_path_segments(source: Path) -> int | None:
    """Primer segmento ``YYYY`` (1950–2035) en la ruta relativa bajo ``data/cnv``."""
    try:
        for part in source.resolve().parts:
            if len(part) == 4 and part.isdigit():
                y = int(part)
                if 1950 <= y <= 2035:
                    return y
    except (OSError, ValueError):
        pass
    return None


def year_from_filename_stem(stem: str) -> int | None:
    """Año desde nombre de fichero: ``apr94`` → 1994, ``gnov105`` → 2005, ``cnov117`` → 2017."""
    s = stem.lower().strip()
    if not s:
        return None
    m = _FILENAME_MONTH_YEAR_SUFFIX_RE.search(s)
    if m:
        return _two_digit_year_to_full(int(m.group(1)))
    m_tail = _FILENAME_TAIL_YEAR_RE.search(s)
    if m_tail:
        return _two_digit_year_to_full(int(m_tail.group(1)))
    return None


def reconcile_start_time_year(start_time_iso: str | None, source: Path) -> str | None:
    """
    Sustituye el año de ``start_time_iso`` usando carpeta ``YYYY/`` o el nombre del fichero.

    Conserva mes, día y hora del ``# start_time`` parseado.
    """
    if not start_time_iso or len(start_time_iso) < 10:
        return start_time_iso

    true_year = year_from_path_segments(source)
    if true_year is None:
        true_year = year_from_filename_stem(source.stem)
    if true_year is None:
        return start_time_iso

    return f"{true_year:04d}{start_time_iso[4:]}"


def explain_sampling_year(source: Path) -> dict[str, int | str | None]:
    """
    Explica de dónde sale el año aplicado a ``fecha`` tras ``reconcile_start_time_year``.

    Prioridad aplicada: carpeta ``YYYY/`` > sufijo del nombre de fichero > cabecera sin cambio.
    """
    header_raw: int | None = None
    try:
        with source.open(encoding="latin-1", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= 8000:
                    break
                stripped = line.strip()
                if stripped.upper() == "*END*":
                    break
                m = CNV_START_TIME_RE.search(stripped)
                if m:
                    header_raw = int(m.group(3))
                    break
    except OSError:
        pass

    y_path = year_from_path_segments(source)
    y_file = year_from_filename_stem(source.stem)
    rule = "none"
    if y_path is not None:
        rule = "path"
    elif y_file is not None:
        rule = "filename"
    elif header_raw is not None:
        rule = "header_only"

    iso = parse_cnv_start_time_iso_from_path(source)
    y_applied: int | None = None
    if iso and len(iso) >= 4:
        try:
            y_applied = int(iso[:4])
        except ValueError:
            y_applied = None

    return {
        "year_from_header_raw": header_raw,
        "year_from_path": y_path,
        "year_from_filename": y_file,
        "year_applied": y_applied,
        "rule": rule,
        "start_time_iso_final": iso,
    }


def parse_cnv_column_names_from_path(source: Path, *, max_header_lines: int = 8000) -> list[str] | None:
    """Lee hasta ``*END*`` y devuelve nombres de variable en minúsculas (orden SBE)."""
    names: list[str] = []
    try:
        with source.open(encoding="latin-1", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_header_lines:
                    break
                stripped = line.strip()
                if stripped.upper() == "*END*":
                    break
                m = CNV_NAME_LINE_RE.match(stripped)
                if m:
                    names.append(m.group(1).strip().lower())
        return names if names else None
    except OSError:
        return None


def cnv_header_has_start_time(source: Path, *, max_header_lines: int = 8000) -> bool:
    """True si existe una línea ``# start_time =`` (fecha de inicio de muestreo)."""
    try:
        with source.open(encoding="latin-1", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_header_lines:
                    break
                if line.strip().upper().startswith("*END*"):
                    break
                if CNV_START_TIME_RE.search(line.strip()):
                    return True
        return False
    except OSError:
        return False


def _start_time_iso_from_match(m: re.Match[str]) -> str | None:
    mon_str = m.group(1).lower()[:3]
    mon = _MONTHS.get(mon_str)
    if not mon:
        return None
    day = int(m.group(2))
    year = int(m.group(3))
    hh, mm, ss = int(m.group(4)), int(m.group(5)), int(m.group(6))
    return f"{year:04d}-{mon:02d}-{day:02d}T{hh:02d}:{mm:02d}:{ss:02d}"


def parse_cnv_start_time_iso_from_path(source: Path, *, max_header_lines: int = 8000) -> str | None:
    """ISO ``YYYY-MM-DDTHH:MM:SS`` desde ``# start_time = Mon DD YYYY HH:MM:SS``."""
    try:
        with source.open(encoding="latin-1", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_header_lines:
                    break
                stripped = line.strip()
                if stripped.upper() == "*END*":
                    break
                m = CNV_START_TIME_RE.search(stripped)
                if m:
                    iso = _start_time_iso_from_match(m)
                    return reconcile_start_time_year(iso, source)
        return None
    except OSError:
        return None


def parse_cnv_station_number_from_path(source: Path, *, max_header_lines: int = 200) -> int | None:
    """Número de estación desde ``** Station:   N`` en cabecera SBE."""
    try:
        with source.open(encoding="latin-1", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_header_lines:
                    break
                m = CNV_STATION_LINE_RE.match(line.strip())
                if m:
                    station_val = m.group(1).strip()
                    m_num = re.search(r"(\d+)", station_val)
                    if m_num:
                        return int(m_num.group(1))
        return None
    except (OSError, ValueError):
        return None


def parse_station_from_folder_name(source: Path) -> int | None:
    """
    Estación desde carpeta padre (``St.1 CNVs`` → 1).

    Radiales Cudillero históricas: St.1/2/3 ↔ E1CU/E2CU/E3CU.
    """
    m = _STATION_FOLDER_RE.search(source.parent.name)
    if m:
        return int(m.group(1))
    return None


def parse_station_from_filename(source: Path) -> int | None:
    """Estación desde nombre (``rcan202510stc3cast018.cnv`` → 3)."""
    m = _STATION_FILE_RE.search(source.name)
    if m:
        return int(m.group(1))
    return None

"""
Utilidades compartidas para cabeceras SeaBird ``.cnv``.

Los ficheros IEO suelen ser SBE 19/25 con líneas ``# name N = var: descripción`` donde
``var`` puede contener ``/`` (p.ej. ``c0S/m``). El patrón antiguo ``\\w+`` fallaba y
dejaba columnas fuera, lo que vaciaba la lista y mandaba todo a cuarentena.

También muchos .cnv **no** traen ``timeJ`` en columnas: solo ``# start_time =`` en
cabecera; la puerta debe aceptar ese caso.
"""

from __future__ import annotations

import re
from pathlib import Path

# ``# name 0 = prSM: ...`` o ``# name 2 = c0S/m: ...``
CNV_NAME_LINE_RE = re.compile(r"^#\s+name\s+\d+\s*=\s*(.+?)\s*:\s*", re.IGNORECASE)

# ``# start_time = Jul 17 2001 11:54:25`` (mes abreviado en inglés)
CNV_START_TIME_RE = re.compile(
    r"^#\s*start_time\s*=\s*"
    r"(\w+)\s+(\d+)\s+(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})",
    re.IGNORECASE,
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ``** Station:    6`` o ``* Station: 6``
CNV_STATION_LINE_RE = re.compile(
    r"^\*+\s*Station:\s*(\d+)",
    re.IGNORECASE,
)


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
                    mon_str = m.group(1).lower()[:3]
                    mon = _MONTHS.get(mon_str)
                    if not mon:
                        return None
                    day = int(m.group(2))
                    year = int(m.group(3))
                    hh, mm, ss = int(m.group(4)), int(m.group(5)), int(m.group(6))
                    return f"{year:04d}-{mon:02d}-{day:02d}T{hh:02d}:{mm:02d}:{ss:02d}"
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
                    return int(m.group(1))
        return None
    except (OSError, ValueError):
        return None

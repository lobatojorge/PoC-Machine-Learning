"""
Clasificación de ficheros SeaBird ``.cnv`` por radial a partir de metadatos y nombre.

Orden de precedencia (producto radial):
1. Posición **lat/lon** del cast (cabecera SBE), salvo cruise vacío → filename primero.
2. ``** Cruise:`` con nombre explícito de radial (incl. ``RADCAN… Cudillero``).
3. Nombre de fichero (prefijos históricos).
4. Bbox Cudillero legacy si cruise vacío.

``RCAN`` / ``Radiales Cantábrico`` indican **campaña**; la radial se fija por coords o texto.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ieo.radiales_catalog import (
    RADIAL_ID_CORUNA,
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_GIJON,
    RADIAL_ID_SANTANDER,
    RADIAL_ID_VIGO,
    identify_radial,
)

CNV_CRUISE_LINE_RE = re.compile(r"^\*+\s*Cruise:\s*(.*)\s*$", re.IGNORECASE)
CNV_LAT_LINE_RE = re.compile(r"^\*{2,}\s*Latitude:\s*(.*)\s*$", re.IGNORECASE)
CNV_LON_LINE_RE = re.compile(r"^\*{2,}\s*Longitude:\s*(.*)\s*$", re.IGNORECASE)
CNV_NMEA_LAT_RE = re.compile(r"^\*\s*NMEA Latitude\s*=\s*(.*)\s*$", re.IGNORECASE)
CNV_NMEA_LON_RE = re.compile(r"^\*\s*NMEA Longitude\s*=\s*(.*)\s*$", re.IGNORECASE)
CNV_STATION_FIELD_RE = re.compile(r"^\*{2,}\s*Station:\s*(.*)\s*$", re.IGNORECASE)

_MONTH_PREFIX_RE = re.compile(
    r"^(?P<prefix>[a-z]{0,2})"
    r"(?P<mon>jan|feb|mar|apr|may|jun|jul|ago|sep|oct|nov|dic|ene)\d",
    re.IGNORECASE,
)

_PREFIX_TO_RADIAL: dict[str, str] = {
    "g": RADIAL_ID_GIJON,
    "s": RADIAL_ID_SANTANDER,
}

# Topónimos asturianos / variantes en ``** Cruise:`` (clave = texto normalizado).
LOCALITY_ALIASES_ASTURIAN: dict[str, str] = {
    "cuideiru": RADIAL_ID_CUDILLERO,
    "xixon": RADIAL_ID_GIJON,
}

_CRUISE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (RADIAL_ID_CUDILLERO, ("cudillero", "cuideiru", "radial cud", "rad. cud")),
    (RADIAL_ID_GIJON, ("gijon", "gijón", "gij\x95n", "xixon", "radial gij", "radial de gij", "jureva")),
    (RADIAL_ID_SANTANDER, ("santander", "santand", "sanatnder", "sanatander", "rad san", "radsan")),
    (RADIAL_ID_VIGO, ("vigo", "radial vi", "rad vi")),
    (RADIAL_ID_CORUNA, ("coru", "coruña", "coruna", "la coru", "a coru")),
)

_RCAN_CAMPAIGN_RE = re.compile(
    r"rcan|radcan|radial_can|radprof|radiales?\s+cant[aá]bric",
    re.IGNORECASE,
)

_CUDILLERO_LAT_MIN = 43.2
_CUDILLERO_LAT_MAX = 43.95
_CUDILLERO_LON_MIN = -6.5
_CUDILLERO_LON_MAX = -3.0


@dataclass(frozen=True, slots=True)
class CnvRadialHints:
    cruise: str = ""
    latitude: str = ""
    longitude: str = ""
    lat_deg: float | None = None
    lon_deg: float | None = None
    station_field: str = ""  # raw value of ** Station:


@dataclass(frozen=True, slots=True)
class CnvRadialClassification:
    radial_id: str | None
    rule: str
    campana_rcan: bool = False
    cruise_radial: str | None = None
    geo_radial: str | None = None
    conflict_cruise_vs_geo: bool = False


def _parse_lat_lon_deg(lat_str: str, lon_str: str) -> tuple[float | None, float | None]:
    def lat_to_deg(s: str) -> float | None:
        s = s.strip().upper()
        if not s:
            return None
        s = re.sub(r"[^0-9A-Z\s\.\-+]", " ", s)
        parts = s.replace("N", "").replace("S", "").split()
        try:
            nums = [float(p) for p in parts[:3]]
        except ValueError:
            return None
        if not nums:
            return None
        deg = nums[0] + (nums[1] / 60.0 if len(nums) > 1 else 0.0)
        if len(nums) > 2:
            deg += nums[2] / 3600.0
        if "S" in s:
            deg = -deg
        return deg

    def lon_to_deg(s: str) -> float | None:
        s = s.strip().upper()
        if not s:
            return None
        s = re.sub(r"[^0-9A-Z\s\.\-+]", " ", s)
        parts = s.replace("E", "").replace("W", "").split()
        try:
            nums = [float(p) for p in parts[:3]]
        except ValueError:
            return None
        if not nums:
            return None
        deg = nums[0] + (nums[1] / 60.0 if len(nums) > 1 else 0.0)
        if len(nums) > 2:
            deg += nums[2] / 3600.0
        if "W" in s:
            deg = -deg
        return deg

    return lat_to_deg(lat_str), lon_to_deg(lon_str)



def read_cnv_radial_hints(source: Path, *, max_header_lines: int = 200) -> CnvRadialHints:
    cruise = latitude = longitude = station_field = ""
    nmea_lat = nmea_lon = ""
    try:
        with source.open(encoding="latin-1", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_header_lines:
                    break
                if line.strip().upper() == "*END*":
                    break
                st = line.strip()
                m = CNV_CRUISE_LINE_RE.match(st)
                if m:
                    cruise = m.group(1).strip()
                m = CNV_LAT_LINE_RE.match(st)
                if m:
                    latitude = m.group(1).strip()
                m = CNV_LON_LINE_RE.match(st)
                if m:
                    longitude = m.group(1).strip()
                m = CNV_NMEA_LAT_RE.match(st)
                if m:
                    nmea_lat = m.group(1).strip()
                m = CNV_NMEA_LON_RE.match(st)
                if m:
                    nmea_lon = m.group(1).strip()
                m = CNV_STATION_FIELD_RE.match(st)
                if m:
                    station_field = m.group(1).strip()
    except OSError as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "cnv_radial: could not read header hints for %s (%s); "
            "radial classification will fall back to filename only.",
            source.name, exc,
        )
    # Use ** Latitude/Longitude when available; fall back to * NMEA Latitude/Longitude
    eff_lat = latitude if latitude else nmea_lat
    eff_lon = longitude if longitude else nmea_lon
    lat_d, lon_d = _parse_lat_lon_deg(eff_lat, eff_lon)
    return CnvRadialHints(
        cruise=cruise,
        latitude=eff_lat,
        longitude=eff_lon,
        lat_deg=lat_d,
        lon_deg=lon_d,
        station_field=station_field,
    )


def normalize_cruise_text(cruise: str) -> str:
    """Minúsculas, sin acentos, espacios colapsados (para alias asturiano y keywords)."""
    if not cruise:
        return ""
    s = unicodedata.normalize("NFKD", str(cruise))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    return " ".join(s.split())


def _radial_from_asturian_aliases(cruise: str) -> str | None:
    norm = normalize_cruise_text(cruise)
    if not norm:
        return None
    for alias, radial_id in LOCALITY_ALIASES_ASTURIAN.items():
        if alias in norm:
            return radial_id
    return None


def is_rcan_campaign(cruise: str) -> bool:
    """True si el cruise indica campaña Cantábrico (RCAN, etc.), sin nombre de radial."""
    c = (cruise or "").lower()
    if not _RCAN_CAMPAIGN_RE.search(c):
        return False
    for _, keywords in _CRUISE_KEYWORDS:
        if any(k in c for k in keywords):
            return False
    return True


def classify_radial_by_position(lat_deg: float | None, lon_deg: float | None) -> str | None:
    """
    Franjas lon/lat Cantábrico sin solapes graves.

    A Coruña **no** usa la regla antigua ``lat >= 43.85 y lon <= -5`` (etiquetaba mar al norte
    de Gijón como Coruña). Galicia occidental: ``lon <= -7`` con latitudes típicas de la
    costa/plataforma gallega; se evalúa **antes** que la franja ``lon <= -6`` de Cudillero.
    """
    if lat_deg is None or lon_deg is None:
        return None
    if lat_deg < 43.15 or lat_deg > 44.7 or lon_deg > -2.5 or lon_deg < -9.5:
        return None
    if lon_deg <= -7.5 and 43.05 <= lat_deg <= 44.35:
        return RADIAL_ID_CORUNA
    if lon_deg <= -6.0:
        return RADIAL_ID_CUDILLERO
    if lon_deg <= -4.85:
        return RADIAL_ID_GIJON
    return RADIAL_ID_SANTANDER


def _radial_from_cruise_explicit(cruise: str) -> str | None:
    if not cruise:
        return None
    ast = _radial_from_asturian_aliases(cruise)
    if ast is not None:
        return ast
    c = normalize_cruise_text(cruise)
    for radial_id, keywords in _CRUISE_KEYWORDS:
        if any(k in c for k in keywords):
            return radial_id
    if is_rcan_campaign(cruise):
        return None
    return None


def _radial_from_filename(name: str) -> str | None:
    lower = name.lower()
    stem = Path(name).stem.lower()

    rid = identify_radial(stem.upper())
    if rid:
        return rid

    if stem.startswith(("gseprt", "gagort", "gago")):
        return RADIAL_ID_GIJON

    if lower.startswith("rcan"):
        return None

    m = _MONTH_PREFIX_RE.match(stem)
    if m:
        prefix = m.group("prefix") or ""
        if prefix in _PREFIX_TO_RADIAL:
            return _PREFIX_TO_RADIAL[prefix]
        if not prefix:
            return RADIAL_ID_CUDILLERO

    if re.match(r"^(\d+)?(ene|feb|mar|apr|may|jun|jul|ago|sep|oct|nov|dic)\d", stem):
        return RADIAL_ID_CUDILLERO

    return None


def _in_cudillero_bbox(hints: CnvRadialHints) -> bool:
    if hints.lat_deg is None or hints.lon_deg is None:
        return False
    return (
        _CUDILLERO_LAT_MIN <= hints.lat_deg <= _CUDILLERO_LAT_MAX
        and _CUDILLERO_LON_MIN <= hints.lon_deg <= _CUDILLERO_LON_MAX
    )


def _is_stn_cudillero_folder(source: Path) -> bool:
    """True si el fichero está en una carpeta 'St.N CNVs' (estaciones históricas de Cudillero)."""
    return bool(re.search(r'[Ss]t\.\d+\s+CNVs?', source.parent.name))


def _radial_from_station_prefix(hints: CnvRadialHints) -> str | None:
    """Deduce radial from ** Station: prefix for RCAN/Radiales campaigns.

    Conventions observed in the field:
      C1, C2, C3  → Cudillero
      G1, G2, ...  → Gijón
      S1, S2, ...  → Santander
    Only applied when cruise matches _RCAN_CAMPAIGN_RE to avoid mis-classifying
    historical files that happen to have a one-letter station code.
    """
    if not is_rcan_campaign(hints.cruise):
        return None
    stn = hints.station_field.strip().upper()
    if not stn:
        return None
    if stn.startswith("CO"):
        return RADIAL_ID_CORUNA
    if stn.startswith("C"):
        return RADIAL_ID_CUDILLERO
    if stn.startswith("G"):
        return RADIAL_ID_GIJON
    if stn.startswith("S"):
        return RADIAL_ID_SANTANDER
    if stn.startswith("V"):
        return RADIAL_ID_VIGO
    return None


def classify_cnv_radial_detailed(source: Path) -> CnvRadialClassification:
    hints = read_cnv_radial_hints(source)
    campana = is_rcan_campaign(hints.cruise)
    geo = classify_radial_by_position(hints.lat_deg, hints.lon_deg)
    cruise_rid = _radial_from_cruise_explicit(hints.cruise)
    file_rid = _radial_from_filename(source.name)
    station_rid = _radial_from_station_prefix(hints)
    conflict = bool(geo and cruise_rid and geo != cruise_rid)


    # Máxima precedencia: carpeta 'St.N CNVs' → siempre Cudillero
    # (ficheros históricos 1993–2003 de las tres estaciones de Cudillero,
    # aunque el campo cruise contenga texto ambiguo como "Radial Gij cudi")
    if _is_stn_cudillero_folder(source):
        if geo and geo != RADIAL_ID_CUDILLERO:
            import warnings
            warnings.warn(
                f"[cnv_radial] stn_cudillero_folder anula clasificación geo={geo!r} "
                f"para {source.name!r}. Verificar que el fichero pertenece a Cudillero.",
                stacklevel=2,
            )
        return CnvRadialClassification(
            radial_id=RADIAL_ID_CUDILLERO,
            rule="stn_cudillero_folder",
            campana_rcan=False,
            cruise_radial=cruise_rid,
            geo_radial=geo,
            conflict_cruise_vs_geo=False,
        )

    if not hints.cruise.strip():
        if file_rid:
            return CnvRadialClassification(
                radial_id=file_rid,
                rule="filename",
                campana_rcan=campana,
                cruise_radial=None,
                geo_radial=geo,
                conflict_cruise_vs_geo=False,
            )
        if geo:
            return CnvRadialClassification(
                radial_id=geo,
                rule="geo",
                campana_rcan=campana,
                cruise_radial=None,
                geo_radial=geo,
                conflict_cruise_vs_geo=False,
            )

    if cruise_rid and not conflict:
        return CnvRadialClassification(
            radial_id=cruise_rid,
            rule="cruise",
            campana_rcan=campana,
            cruise_radial=cruise_rid,
            geo_radial=geo,
            conflict_cruise_vs_geo=False,
        )
    if geo and (not cruise_rid or conflict):
        return CnvRadialClassification(
            radial_id=geo,
            rule="geo",
            campana_rcan=campana,
            cruise_radial=cruise_rid,
            geo_radial=geo,
            conflict_cruise_vs_geo=conflict,
        )
    if file_rid:
        return CnvRadialClassification(
            radial_id=file_rid,
            rule="filename",
            campana_rcan=campana,
            cruise_radial=None,
            geo_radial=geo,
            conflict_cruise_vs_geo=False,
        )
    # Fallback bbox Cudillero: solo se activa cuando classify_radial_by_position devuelve None
    # (coordenadas fuera del Cantábrico conocido) o Cudillero. No se activa si la geo
    # ya resolvió Santander, Gijón, etc., para evitar capturar ficheros de otras radiales.
    geo_compatible = geo is None or geo == RADIAL_ID_CUDILLERO
    if not hints.cruise.strip() and geo_compatible and _in_cudillero_bbox(hints):
        name = source.name.lower()
        if not name.startswith(("g", "s", "rcan")):
            return CnvRadialClassification(
                radial_id=RADIAL_ID_CUDILLERO,
                rule="bbox_cudillero_legacy",
                campana_rcan=False,
                cruise_radial=None,
                geo_radial=geo,
                conflict_cruise_vs_geo=False,
            )

    # Fallback: ** Station: prefix for RCAN campaigns (C/G/S → cudillero/gijon/santander)
    if station_rid:
        return CnvRadialClassification(
            radial_id=station_rid,
            rule="rcan_station_prefix",
            campana_rcan=campana,
            cruise_radial=cruise_rid,
            geo_radial=geo,
            conflict_cruise_vs_geo=conflict,
        )

    return CnvRadialClassification(
        radial_id=None,
        rule="unknown",
        campana_rcan=campana,
        cruise_radial=cruise_rid,
        geo_radial=geo,
        conflict_cruise_vs_geo=conflict,
    )



def classify_cnv_radial(source: Path) -> str | None:
    return classify_cnv_radial_detailed(source).radial_id


def radial_id_from_source_reference(
    ref: str | None,
    *,
    cnv_root: Path | None = None,
) -> str | None:
    """
    Infiere ``radial_id`` desde ``source_file`` / nombre de fichero en un DataFrame.

    Si ``cnv_root`` apunta a ``data/cnv/``, resuelve la ruta real para usar cabecera SBE (geo/cruise).
    """
    if ref is None:
        return None
    name = str(ref).strip()
    if not name:
        return None
    leaf = Path(name).name
    if cnv_root is not None and cnv_root.is_dir():
        hits = sorted(cnv_root.rglob(leaf))
        if hits:
            return classify_cnv_radial(hits[0])
    return classify_cnv_radial(Path(leaf))


def is_cudillero_cnv(source: Path) -> bool:
    return classify_cnv_radial(source) == RADIAL_ID_CUDILLERO


def filter_paths_by_radial(
    candidates: list[Path],
    target_radial: str,
    *,
    cnv_root: Path | None = None,
) -> tuple[list[Path], list[dict[str, Any]], dict[str, int]]:
    kept: list[Path] = []
    skipped_sample: list[dict[str, Any]] = []
    by_radial: dict[str, int] = {}

    for path in candidates:
        rid = classify_cnv_radial(path)
        if rid == target_radial:
            kept.append(path)
            continue
        label = rid or "desconocida"
        by_radial[label] = by_radial.get(label, 0) + 1
        entry: dict[str, Any] = {
            "file": path.name,
            "radial": label,
            "reason": radial_skip_reason(path, target_radial),
        }
        if cnv_root is not None:
            try:
                entry["rel"] = path.resolve().relative_to(cnv_root.resolve()).as_posix()
            except ValueError:
                entry["rel"] = path.name
        if rid is None:
            hints = read_cnv_radial_hints(path)
            cr = (hints.cruise or "").strip()
            if cr:
                entry["cruise_hint"] = cr[:120]
            stn = (hints.station_field or "").strip()
            if stn:
                entry["station_hint"] = stn
        skipped_sample.append(entry)


    return kept, skipped_sample, by_radial



def filter_paths_to_cudillero(
    candidates: list[Path],
    *,
    cnv_root: Path | None = None,
) -> tuple[list[Path], list[dict[str, Any]], dict[str, int]]:
    return filter_paths_by_radial(candidates, RADIAL_ID_CUDILLERO, cnv_root=cnv_root)


def radial_skip_reason(source: Path, target_radial: str) -> str:
    det = classify_cnv_radial_detailed(source)
    hints = read_cnv_radial_hints(source)
    cruise = hints.cruise or "(vacío)"
    if det.radial_id and det.radial_id != target_radial:
        return f"No es radial {target_radial} (detectado: {det.radial_id} por {det.rule}; Cruise: {cruise[:60]})."
    if det.radial_id is None:
        extra = " campaña RCAN/Cantábrico." if det.campana_rcan else ""
        return (
            f"Radial no identificada (Cruise: {cruise[:60]}; nombre: {source.name}).{extra} "
            f"Con alcance de pipeline (`IEO_PIPELINE_RADIAL` / legacy `IEO_ONLY_CUDILLERO`) "
            f"solo se procesa la radial {target_radial}."
        )
    return ""


def cudillero_skip_reason(source: Path) -> str:
    return radial_skip_reason(source, RADIAL_ID_CUDILLERO)

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
from dataclasses import dataclass
from pathlib import Path

from ieo.radiales_catalog import (
    RADIAL_ID_CORUNA,
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_GIJON,
    RADIAL_ID_SANTANDER,
    RADIAL_ID_VIGO,
    identify_radial,
)

CNV_CRUISE_LINE_RE = re.compile(r"^\*+\s*Cruise:\s*(.*)\s*$", re.IGNORECASE)
CNV_LAT_LINE_RE = re.compile(r"^\*+\s*Latitude:\s*(.*)\s*$", re.IGNORECASE)
CNV_LON_LINE_RE = re.compile(r"^\*+\s*Longitude:\s*(.*)\s*$", re.IGNORECASE)

_MONTH_PREFIX_RE = re.compile(
    r"^(?P<prefix>[a-z]{0,2})"
    r"(?P<mon>jan|feb|mar|apr|may|jun|jul|ago|sep|oct|nov|dic|ene)\d",
    re.IGNORECASE,
)

_PREFIX_TO_RADIAL: dict[str, str] = {
    "g": RADIAL_ID_GIJON,
    "s": RADIAL_ID_SANTANDER,
}

_CRUISE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (RADIAL_ID_CUDILLERO, ("cudillero", "radial cud", "rad. cud")),
    (RADIAL_ID_GIJON, ("gijon", "gijón", "gij\x95n", "radial gij", "radial de gij", "jureva")),
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
        elif "E" not in s and 0 < deg < 20:
            deg = -deg
        return deg

    return lat_to_deg(lat_str), lon_to_deg(lon_str)


def read_cnv_radial_hints(source: Path, *, max_header_lines: int = 200) -> CnvRadialHints:
    cruise = latitude = longitude = ""
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
    except OSError:
        pass
    lat_d, lon_d = _parse_lat_lon_deg(latitude, longitude)
    return CnvRadialHints(
        cruise=cruise,
        latitude=latitude,
        longitude=longitude,
        lat_deg=lat_d,
        lon_deg=lon_d,
    )


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
    """Franjas lon/lat sin solape (Cantábrico)."""
    if lat_deg is None or lon_deg is None:
        return None
    if lat_deg < 43.15 or lat_deg > 44.7 or lon_deg > -2.5 or lon_deg < -9.5:
        return None
    if lat_deg >= 43.85 and lon_deg <= -5.0:
        return RADIAL_ID_CORUNA
    if lon_deg <= -6.0:
        return RADIAL_ID_CUDILLERO
    if lon_deg <= -4.85:
        return RADIAL_ID_GIJON
    return RADIAL_ID_SANTANDER


def _radial_from_cruise_explicit(cruise: str) -> str | None:
    if not cruise:
        return None
    c = cruise.lower()
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


def classify_cnv_radial_detailed(source: Path) -> CnvRadialClassification:
    hints = read_cnv_radial_hints(source)
    campana = is_rcan_campaign(hints.cruise)
    geo = classify_radial_by_position(hints.lat_deg, hints.lon_deg)
    cruise_rid = _radial_from_cruise_explicit(hints.cruise)
    file_rid = _radial_from_filename(source.name)
    conflict = bool(geo and cruise_rid and geo != cruise_rid)

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
    if not hints.cruise.strip() and _in_cudillero_bbox(hints):
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


def is_cudillero_cnv(source: Path) -> bool:
    return classify_cnv_radial(source) == RADIAL_ID_CUDILLERO


def filter_paths_by_radial(
    candidates: list[Path],
    target_radial: str,
) -> tuple[list[Path], list[dict[str, str]], dict[str, int]]:
    kept: list[Path] = []
    skipped_sample: list[dict[str, str]] = []
    by_radial: dict[str, int] = {}

    for path in candidates:
        rid = classify_cnv_radial(path)
        if rid == target_radial:
            kept.append(path)
            continue
        label = rid or "desconocida"
        by_radial[label] = by_radial.get(label, 0) + 1
        if len(skipped_sample) < 30:
            skipped_sample.append(
                {
                    "file": path.name,
                    "radial": label,
                    "reason": radial_skip_reason(path, target_radial),
                }
            )

    return kept, skipped_sample, by_radial


def filter_paths_to_cudillero(
    candidates: list[Path],
) -> tuple[list[Path], list[dict[str, str]], dict[str, int]]:
    return filter_paths_by_radial(candidates, RADIAL_ID_CUDILLERO)


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
            f"Solo se procesa {target_radial}."
        )
    return ""


def cudillero_skip_reason(source: Path) -> str:
    return radial_skip_reason(source, RADIAL_ID_CUDILLERO)

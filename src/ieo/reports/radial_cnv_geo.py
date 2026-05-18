"""
Índice geográfico de radiales a partir de cabeceras ``.cnv`` en ``data/cnv/``.

Alimenta el mapa general del visor (localidad) y las estaciones por radial.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from ieo.cudillero_paths import cnv_dir
from ieo.io.cnv_header import parse_cnv_station_number_from_path
from ieo.io.cnv_radial import classify_cnv_radial, read_cnv_radial_hints
from ieo.radiales_catalog import (
    RADIAL_ID_CORUNA,
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_GIJON,
    RADIAL_ID_SANTANDER,
)

# Radiales visibles en el hub del visor (Cantábrico).
VIEWER_RADIAL_IDS: tuple[str, ...] = (
    RADIAL_ID_CUDILLERO,
    RADIAL_ID_GIJON,
    RADIAL_ID_SANTANDER,
    RADIAL_ID_CORUNA,
)

RADIAL_DISPLAY_NAMES: dict[str, str] = {
    RADIAL_ID_CUDILLERO: "Cudillero",
    RADIAL_ID_GIJON: "Gijón",
    RADIAL_ID_SANTANDER: "Santander",
    RADIAL_ID_CORUNA: "A Coruña",
}


@dataclass(frozen=True, slots=True)
class RadialCityMarker:
    radial_id: str
    label: str
    lat: float
    lon: float
    n_cnv: int


@dataclass(frozen=True, slots=True)
class RadialStationMarker:
    estacion: int
    lat: float
    lon: float
    nombre: str
    n_cnv: int


@dataclass
class RadialGeoIndex:
    cities: list[RadialCityMarker] = field(default_factory=list)
    stations_by_radial: dict[str, list[RadialStationMarker]] = field(default_factory=dict)
    n_cnv_scanned: int = 0
    n_with_coords: int = 0


def _median_coord(values: list[float]) -> float:
    return float(median(values))


def build_radial_geo_index(project_root: Path) -> RadialGeoIndex:
    """
    Recorre ``data/cnv/**/*.cnv`` y agrega posición de cast + estación SBE por radial.

    No lee el bloque de datos; solo cabecera (rápido para el mapa inicial).
    """
    root = project_root.resolve()
    cnv_root = cnv_dir(root)
    if not cnv_root.is_dir():
        return RadialGeoIndex()

    city_lats: dict[str, list[float]] = defaultdict(list)
    city_lons: dict[str, list[float]] = defaultdict(list)
    city_counts: dict[str, int] = defaultdict(int)

    st_lats: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    st_lons: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    st_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    n_scanned = 0
    n_coords = 0

    for path in sorted(cnv_root.rglob("*.cnv")):
        n_scanned += 1
        rid = classify_cnv_radial(path)
        if rid not in VIEWER_RADIAL_IDS:
            continue
        hints = read_cnv_radial_hints(path)
        if hints.lat_deg is None or hints.lon_deg is None:
            continue
        n_coords += 1
        lat, lon = float(hints.lat_deg), float(hints.lon_deg)
        city_lats[rid].append(lat)
        city_lons[rid].append(lon)
        city_counts[rid] += 1

        st_num = parse_cnv_station_number_from_path(path)
        if st_num is not None:
            st_lats[rid][int(st_num)].append(lat)
            st_lons[rid][int(st_num)].append(lon)
            st_counts[rid][int(st_num)] += 1

    cities: list[RadialCityMarker] = []
    for rid in VIEWER_RADIAL_IDS:
        if not city_lats[rid]:
            continue
        cities.append(
            RadialCityMarker(
                radial_id=rid,
                label=RADIAL_DISPLAY_NAMES.get(rid, rid.title()),
                lat=_median_coord(city_lats[rid]),
                lon=_median_coord(city_lons[rid]),
                n_cnv=city_counts[rid],
            )
        )

    stations_by: dict[str, list[RadialStationMarker]] = {}
    for rid in VIEWER_RADIAL_IDS:
        markers: list[RadialStationMarker] = []
        for st_num in sorted(st_lats[rid].keys()):
            label = RADIAL_DISPLAY_NAMES.get(rid, rid)
            markers.append(
                RadialStationMarker(
                    estacion=int(st_num),
                    lat=_median_coord(st_lats[rid][st_num]),
                    lon=_median_coord(st_lons[rid][st_num]),
                    nombre=f"Estación {st_num} · {label}",
                    n_cnv=st_counts[rid][st_num],
                )
            )
        if markers:
            stations_by[rid] = markers

    return RadialGeoIndex(
        cities=cities,
        stations_by_radial=stations_by,
        n_cnv_scanned=n_scanned,
        n_with_coords=n_coords,
    )


def stations_to_plotly_dicts(stations: list[RadialStationMarker]) -> list[dict[str, float | int | str]]:
    return [
        {
            "estacion": s.estacion,
            "lat": s.lat,
            "lon": s.lon,
            "nombre": s.nombre,
        }
        for s in stations
    ]

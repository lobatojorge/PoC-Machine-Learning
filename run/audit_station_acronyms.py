#!/usr/bin/env python3
"""
Inventario de Cruise, estación SBE, carpetas St.N y años por fichero ``.cnv``.

Genera:
  - outputs/temporal/station_acronym_audit.csv
  - outputs/temporal/cruise_unique_by_radial.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent
_SRC = (PROJECT_ROOT / "src").resolve()
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ieo.paths import cnv_dir  # noqa: E402
from ieo.io.cnv_header import (  # noqa: E402
    explain_sampling_year,
    parse_cnv_station_number_from_path,
    parse_station_from_folder_name,
)
from ieo.io.cnv_radial import (  # noqa: E402
    _radial_from_asturian_aliases,
    _radial_from_cruise_explicit,
    classify_radial_by_position,
    classify_cnv_radial,
    normalize_cruise_text,
    read_cnv_radial_hints,
)

OUT_AUDIT = PROJECT_ROOT / "outputs" / "temporal" / "station_acronym_audit.csv"
OUT_CRUISE = PROJECT_ROOT / "outputs" / "temporal" / "cruise_unique_by_radial.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría Cruise / estación / año en .cnv")
    parser.add_argument("--radial", default=None, help="Filtrar radial_id (p. ej. gijon)")
    args = parser.parse_args()

    root = cnv_dir(PROJECT_ROOT)
    if not root.is_dir():
        print(f"No existe {root}")
        return 1

    paths = sorted(root.rglob("*.cnv"))
    rows: list[dict[str, str | int]] = []
    cruise_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for p in paths:
        hints = read_cnv_radial_hints(p)
        cruise_raw = hints.cruise
        cruise_norm = normalize_cruise_text(cruise_raw)
        radial_cruise = _radial_from_cruise_explicit(cruise_raw)
        radial_ast = _radial_from_asturian_aliases(cruise_raw)
        radial_geo = classify_radial_by_position(hints.lat_deg, hints.lon_deg)
        radial_final = classify_cnv_radial(p)
        st_sbe = parse_cnv_station_number_from_path(p)
        st_folder = parse_station_from_folder_name(p)
        year_info = explain_sampling_year(p)

        if args.radial and radial_final != args.radial:
            continue

        rel = str(p.relative_to(PROJECT_ROOT))
        parent = p.parent.name
        rows.append(
            {
                "path": rel,
                "file": p.name,
                "parent_folder": parent,
                "cruise_raw": cruise_raw[:200],
                "cruise_normalized": cruise_norm[:200],
                "radial_id_cruise": radial_cruise or "",
                "radial_id_asturian": radial_ast or "",
                "radial_id_geo": radial_geo or "",
                "radial_id_final": radial_final or "",
                "station_sbe": st_sbe if st_sbe is not None else "",
                "station_folder": st_folder if st_folder is not None else "",
                "year_header_raw": year_info.get("year_from_header_raw") or "",
                "year_path": year_info.get("year_from_path") or "",
                "year_file": year_info.get("year_from_filename") or "",
                "year_applied": year_info.get("year_applied") or "",
                "year_rule": year_info.get("rule") or "",
            }
        )
        rid_key = radial_final or "desconocida"
        if cruise_raw.strip():
            cruise_counts[rid_key][cruise_raw.strip()] += 1

    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with OUT_AUDIT.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    cruise_rows: list[dict[str, str | int]] = []
    for rid, ctr in sorted(cruise_counts.items()):
        for cruise, n in ctr.most_common():
            cruise_rows.append(
                {
                    "radial_id": rid,
                    "cruise_raw": cruise,
                    "cruise_normalized": normalize_cruise_text(cruise),
                    "n_files": n,
                }
            )
    if cruise_rows:
        with OUT_CRUISE.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(cruise_rows[0].keys()))
            w.writeheader()
            w.writerows(cruise_rows)

    unclassified = Counter()
    for r in rows:
        if not r["radial_id_cruise"] and not r["radial_id_asturian"] and r["cruise_raw"]:
            unclassified[str(r["cruise_raw"])[:80]] += 1

    print(f"Ficheros auditados: {len(rows)}")
    print(f"  {OUT_AUDIT}")
    print(f"  {OUT_CRUISE}")
    if unclassified:
        print("Top Cruise sin radial por texto (revisar glosario):")
        for text, n in unclassified.most_common(15):
            print(f"  [{n:4d}] {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

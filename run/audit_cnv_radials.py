#!/usr/bin/env python3
"""
Auditoría de clasificación radial en ``data/cnv/``.

Genera ``outputs/temporal/cnv_radial_audit.csv`` con coords, cruise, radial y regla.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent
_SRC = (PROJECT_ROOT / "src").resolve()
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ieo.cudillero_paths import cnv_dir  # noqa: E402
from ieo.io.cnv_header import parse_cnv_station_number_from_path  # noqa: E402
from ieo.io.cnv_radial import classify_cnv_radial_detailed, read_cnv_radial_hints  # noqa: E402

OUT_CSV = PROJECT_ROOT / "outputs" / "temporal" / "cnv_radial_audit.csv"


def main() -> int:
    paths = sorted(cnv_dir(PROJECT_ROOT).rglob("*.cnv"))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | float | bool]] = []
    for p in paths:
        hints = read_cnv_radial_hints(p)
        det = classify_cnv_radial_detailed(p)
        st = parse_cnv_station_number_from_path(p)
        rows.append(
            {
                "file": p.name,
                "path": str(p.relative_to(PROJECT_ROOT)),
                "cruise": hints.cruise[:120],
                "lat_deg": hints.lat_deg if hints.lat_deg is not None else "",
                "lon_deg": hints.lon_deg if hints.lon_deg is not None else "",
                "station": st if st is not None else "",
                "radial_id": det.radial_id or "desconocida",
                "rule": det.rule,
                "campana_rcan": det.campana_rcan,
                "conflict_cruise_vs_geo": det.conflict_cruise_vs_geo,
            }
        )

    fields = list(rows[0].keys()) if rows else []
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    n_unk = sum(1 for r in rows if r["radial_id"] == "desconocida")
    n_rcan = sum(1 for r in rows if r["campana_rcan"])
    print(f"[ok] {len(rows)} ficheros -> {OUT_CSV}")
    print(f"     desconocida: {n_unk} | campana RCAN/Cantabrico: {n_rcan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Puerta de ingesta: columnas de presión SBE antiguas (``pr``, ``deps``)."""

from __future__ import annotations

from pathlib import Path

from ieo.ingest_gate import evaluate_file


def _minimal_cnv_with_pr() -> str:
    return "\n".join(
        [
            "* Sea-Bird",
            "** Cruise: Radial 01/2000",
            "# name 0 = t068: temperature [deg C]",
            "# name 1 = pr: pressure [db]",
            "# start_time = Jan 13 2000 10:28:25",
            "*END*",
            "1 2.0",
        ]
    )


def test_gate_accepts_pr_pressure_column(tmp_path: Path) -> None:
    f = tmp_path / "legacy.cnv"
    f.write_text(_minimal_cnv_with_pr(), encoding="latin-1")
    r = evaluate_file(f, project_root=tmp_path)
    assert r.accepted is True
    assert not r.reasons

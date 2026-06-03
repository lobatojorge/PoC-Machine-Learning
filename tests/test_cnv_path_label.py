"""Etiquetas de ruta bajo data/cnv/ y formato de resumen de ingesta."""

from __future__ import annotations

from pathlib import Path

from ieo.paths import cnv_file_label_under_root
from ieo.reports.resumen_ultima import format_ingest_console


def test_cnv_file_label_year_folder(tmp_path: Path) -> None:
    cnv = tmp_path / "cnv"
    (cnv / "2019").mkdir(parents=True)
    f = cnv / "2019" / "foo.cnv"
    f.write_text("x", encoding="utf-8")
    assert cnv_file_label_under_root(cnv, f) == "2019/foo.cnv"


def test_cnv_file_label_nested_no_year_prefix(tmp_path: Path) -> None:
    cnv = tmp_path / "cnv"
    (cnv / "misc" / "a").mkdir(parents=True)
    f = cnv / "misc" / "a" / "bar.cnv"
    f.write_text("x", encoding="utf-8")
    assert cnv_file_label_under_root(cnv, f) == "misc/a/bar.cnv"


def test_format_ingest_console_includes_inventory_block() -> None:
    text = format_ingest_console(
        {
            "inventario_por_radial": {"gijon": 3, "cudillero": 2},
            "inventario_total": 5,
            "filtro_radial": "todas",
            "n_cudillero_candidatos": 2,
            "n_omitidas_otra_radial": 3,
            "n_puerta_ok": 2,
            "n_cuarentena": 0,
            "n_parquet_canonicos": 0,
            "n_error_tras_puerta": 0,
            "copias_a_data_checked": 0,
        }
    )
    assert "Inventario data/cnv" in text
    assert "Gijón" in text
    assert "Esta ejecución" in text

# -*- coding: utf-8 -*-
"""Etiquetas cortas de errores de ingesta (cli)."""

from __future__ import annotations

from ieo.cli import _short_ingest_error_label


def test_short_label_estacion() -> None:
    msg = "Faltan columnas requeridas tras normalizaci\u00f3n: ['estacion']. Columnas: ['fecha']"
    assert _short_ingest_error_label(ValueError(msg)) == "Falta columna estaci\u00f3n tras normalizaci\u00f3n"


def test_short_label_sin_datos() -> None:
    exc = ValueError("No se encontraron datos tras la cabecera de foo.cnv.")
    assert _short_ingest_error_label(exc) == "Sin datos tras cabecera (*END*)"

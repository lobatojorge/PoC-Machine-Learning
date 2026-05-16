"""
Materializa ``data/processed/perfiles_all.csv`` desde ``data/raw/perfiles_all.csv``.

El CSV raw (columnas típicas: file, perfil, Fecha, Est, Press, Temp, Sal) se convierte al
esquema del visor y del pipeline: fecha, estacion, profundidad_m, temperatura_c,
salinidad_psu, acronimo (clave de lance).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parent


def build_processed(*, project_root: Path, raw_name: str = "perfiles_all.csv") -> Path:
    import polars as pl

    raw = project_root / "data" / "raw" / raw_name
    out = project_root / "data" / "processed" / "perfiles_all.csv"
    if not raw.is_file():
        raise FileNotFoundError(f"No existe el CSV raw: {raw}")

    out.parent.mkdir(parents=True, exist_ok=True)

    lf = pl.scan_csv(
        raw,
        infer_schema_length=200_000,
        low_memory=True,
        null_values=["", "NA", "NaN", "null"],
        schema_overrides={"Press": pl.Float64, "Temp": pl.Float64, "Sal": pl.Float64},
    )

    lf = lf.with_columns(
        pl.col("Fecha").str.to_datetime("%Y-%m-%d", strict=False).alias("fecha"),
        pl.col("Press").cast(pl.Float64).alias("profundidad_m"),
        pl.col("Temp").cast(pl.Float64).alias("temperatura_c"),
        pl.col("Sal").cast(pl.Float64, strict=False).alias("salinidad_psu"),
        pl.col("Est")
        .cast(pl.Utf8)
        .str.extract(r"^E(\d+)", 1)
        .cast(pl.Int64, strict=False)
        .alias("estacion"),
        pl.concat_str(
            [pl.col("file").cast(pl.Utf8), pl.lit("|"), pl.col("perfil").cast(pl.Utf8), pl.lit("|"), pl.col("Est")],
            separator="",
        ).alias("acronimo"),
    )

    lf = (
        lf.select(["fecha", "estacion", "profundidad_m", "temperatura_c", "salinidad_psu", "acronimo"])
        .filter(
            pl.col("fecha").is_not_null()
            & pl.col("estacion").is_not_null()
            & pl.col("profundidad_m").is_not_null()
            & pl.col("temperatura_c").is_not_null()
        )
        .sort(["estacion", "fecha", "profundidad_m"])
    )

    tmp = out.with_suffix(".csv.tmp")
    lf.sink_csv(tmp)
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Raw perfiles_all → data/processed/perfiles_all.csv")
    p.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    p.add_argument("--raw-name", type=str, default="perfiles_all.csv", help="Nombre del fichero en data/raw/")
    args = p.parse_args(argv)

    try:
        outp = build_processed(project_root=args.project_root.resolve(), raw_name=args.raw_name)
    except Exception as exc:
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"[ok] Escrito: {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

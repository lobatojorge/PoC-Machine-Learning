"""
Control previo (ingest_gate) para ficheros SeaBird ``.cnv`` antes de la ingesta del pipeline.

Comprobaciones (nivel fichero):
1. Existencia y extensión ``.cnv``.
2. Tamaño > 0.
3. Cabecera con líneas ``# name N = var: ...`` (``var`` puede incluir ``/``, p.ej. ``c0S/m``).
4. Evidencia mínima CTD: temperatura, profundidad/presión, y tiempo (columna **o** ``# start_time =``).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ieo.io.cnv_header import (
    cnv_header_has_start_time,
    parse_cnv_column_names_from_path,
)

# Columnas en cabecera SBE (minúsculas tras parseo)
_TEMP_CANDIDATES = {
    "temperatura_c", "temperatura", "temp", "temperature",
    "t090c", "t068", "t068c", "tv290c", "ts068", "potemp068", "potemp068c",
}
_PROF_CANDIDATES = {
    "profundidad_m", "profundidad", "depth", "dep", "depsm", "deps", "dep_sm",
    "prdm", "prdm [m]", "prsm", "prsm [db]",
    # Presión en psi (``prSE``) solo si no hay profundidad en metros
    "prse",
    "press",
    "pr",
    "sigma0", "sigma-theta", "sigma_theta",
}
_TIME_COL_CANDIDATES = {
    "fecha", "date", "datetime", "time", "timestamp",
    "timej", "timejv2", "time_s",
}

_ACCEPTED_EXTENSIONS = {".cnv"}


@dataclass(frozen=True, slots=True)
class GateResult:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    quarantine_path: Path | None = None


def evaluate_file(source: Path, *, project_root: Path) -> GateResult:
    reasons: list[str] = []

    if not source.exists():
        reasons.append(f"El fichero no existe: {source}")
        return GateResult(accepted=False, reasons=reasons)

    ext = source.suffix.lower()
    if ext not in _ACCEPTED_EXTENSIONS:
        reasons.append(
            f"Extensión no reconocida: '{source.suffix}'. Solo se aceptan ficheros .cnv (SeaBird)."
        )

    if source.stat().st_size == 0:
        reasons.append("El fichero está vacío (0 bytes).")

    if reasons:
        return _quarantine(source, project_root=project_root, reasons=reasons)

    cols = parse_cnv_column_names_from_path(source)
    if cols is None:
        reasons.append(
            "No se pudieron detectar columnas en la cabecera "
            "(¿formato distinto a SeaBird # name N = var: …?)."
        )
        return _quarantine(source, project_root=project_root, reasons=reasons)

    col_set = set(cols)

    if not (_TEMP_CANDIDATES & col_set):
        has_ctd_vars = bool(
            col_set
            & (
                _TEMP_CANDIDATES
                | {"c0s/m", "c1s/m", "sal00", "salinity", "sal"}
            )
        )
        aux = {"par", "spar", "fls", "oxygen", "oxymg", "sbeoxymg", "sbeoxymol"} & col_set
        hint = (
            " Parece perfil auxiliar (p. ej. PAR/fluor sin temperatura ni salinidad), no un cast CTD estándar."
            if aux and not has_ctd_vars
            else ""
        )
        reasons.append(
            "No se encontró columna de temperatura en cabecera "
            f"(se esperaba p.ej. t090C).{hint} "
            f"Columnas detectadas: {cols[:12]}{'…' if len(cols) > 12 else ''}."
        )
    if not (_PROF_CANDIDATES & col_set):
        reasons.append(
            "No se encontró columna de presión/profundidad en cabecera "
            f"(se esperaba p.ej. prSM, prDM). Columnas detectadas: {cols[:12]}{'…' if len(cols) > 12 else ''}."
        )

    has_time_col = bool(_TIME_COL_CANDIDATES & col_set)
    has_start_time = cnv_header_has_start_time(source)
    if not has_time_col and not has_start_time:
        reasons.append(
            "No hay columna de tiempo en datos ni línea '# start_time =' en cabecera."
        )

    if reasons:
        return _quarantine(source, project_root=project_root, reasons=reasons)

    return GateResult(accepted=True)


def _quarantine(source: Path, *, project_root: Path, reasons: list[str]) -> GateResult:
    q_dir = project_root / "data" / "quarantine"
    q_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = q_dir / f"{ts}_{source.name}"

    try:
        shutil.copy2(source, dest)
    except Exception as exc:
        reasons.append(f"[aviso] No se pudo copiar a cuarentena: {exc}")
        return GateResult(accepted=False, reasons=reasons, quarantine_path=None)

    reasons_path = dest.with_suffix(".reasons.json")
    reasons_path.write_text(
        json.dumps(
            {
                "source": str(source),
                "quarantine_copy": str(dest),
                "evaluated_at_utc": ts,
                "reasons": reasons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return GateResult(accepted=False, reasons=reasons, quarantine_path=dest)

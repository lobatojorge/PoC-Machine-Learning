"""
Salida estructurada del pipeline en consola (stderr).

Secciones:
  1. Datos de entrada
  2. Pasos que sufren los datos
  3. Progreso (barras; sin volcar listados ni código)
  4. Resultados consultables
  5. Cómo abrir el visor Streamlit
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ieo.pipeline_env import PIPELINE_RADIAL_ENV
from ieo.radial_labels import label_es

_WIDTH = 72

_PIPELINE_STEPS: list[tuple[str, str]] = [
    (
        "00 · Control previo",
        "Comprueba cabecera y columnas mínimas; rechazos → data/quarantine/",
    ),
    (
        "01 · Ingesta CTD",
        "SeaBird .cnv → tabla canónica → Parquet por perfil (*_ctd_canonical.parquet)",
    ),
    (
        "01b · Contrato radial",
        "Rangos físicos de T, S y profundidad; avisos en checkpoints",
    ),
    (
        "02 · Calidad y anomalías",
        "Isolation Forest por perfil → clean / anomalies / audit (sin listado en consola)",
    ),
    (
        "03 · Consolidación",
        "Une perfiles en perfiles_all.ctd_clean.parquet (entrada principal del visor)",
    ),
]


def _emit(msg: str = "") -> None:
    print(msg, file=sys.stderr)


def _section_title(n: int, title: str) -> None:
    _emit("")
    _emit("─" * _WIDTH)
    _emit(f"  {n}. {title}")
    _emit("─" * _WIDTH)


class PipelineConsole:
    """Orquesta la narrativa de consola de una ejecución."""

    def __init__(self, *, project_root: Path, run_id: str) -> None:
        self.project_root = project_root.resolve()
        self.run_id = run_id
        self.run_root = self.project_root / "outputs" / "runs" / run_id
        self.data_dir = self.run_root / "data"
        self.checkpoints_dir = self.run_root / "checkpoints"

    def banner(self) -> None:
        _emit("")
        _emit("=" * _WIDTH)
        _emit("  IEO Orchestrator — pipeline CTD (producción)".center(_WIDTH))
        _emit("=" * _WIDTH)

    def section_data_inputs(
        self,
        *,
        ingest: dict[str, Any],
        incremental: bool,
        n_gate_eval: int,
    ) -> None:
        _section_title(1, "Datos de entrada")
        _emit(f"  Carpeta fuente     data/cnv/  ({ingest.get('inventario_total', 0)} ficheros .cnv)")
        inv = ingest.get("inventario_por_radial") or {}
        if inv:
            w = max((len(label_es(r)) for r in inv), default=8)
            _emit("  Por ciudad/radial:")
            for rid, count in sorted(inv.items(), key=lambda x: (-x[1], x[0])):
                _emit(f"    {label_es(rid):<{w}}  {count:>5}")
        filtro = str(ingest.get("filtro_radial", "todas"))
        if filtro == "todas":
            _emit("  Alcance pipeline   Todas las radiales")
        else:
            _emit(f"  Alcance pipeline   {label_es(filtro)}  ({PIPELINE_RADIAL_ENV}={filtro})")
        if incremental:
            _emit("  Modo               Incremental (solo .cnv nuevos o modificados)")
            _emit("  Caché              outputs/artifact_cache/ + pipeline_manifest.json")
        else:
            _emit("  Modo               Reconstrucción completa (IEO_FULL_REBUILD=1)")
        _emit(f"  A evaluar (puerta) {n_gate_eval} ficheros")

    def section_pipeline_steps(self) -> None:
        _section_title(2, "Pasos que sufren los datos")
        for i, (name, desc) in enumerate(_PIPELINE_STEPS, start=1):
            _emit(f"  {i}) {name}")
            _emit(f"     {desc}")

    def section_progress_begin(self) -> None:
        _section_title(3, "Progreso")

    def step_done(self, step: str, detail: str) -> None:
        _emit(f"  ✓ {step} — {detail}")

    def step_warn(self, msg: str) -> None:
        _emit(f"  ! {msg}")

    def section_results(
        self,
        *,
        exit_code: int,
        ingest: dict[str, Any],
        steps_ok: list[str],
        steps_failed: list[str],
        n_anomalies: int,
        contract_errors: int,
        n_quarantine: int,
        n_qc_errors: int,
        artifacts: dict[str, str],
        logbook_name: str | None,
    ) -> None:
        _section_title(4, "Resultados consultables")
        status = {0: "Completado", 1: "Con avisos", 2: "Sin .cnv", 3: "Todo rechazado en puerta"}.get(
            exit_code, "Desconocido"
        )
        _emit(f"  Run ID             {self.run_id}")
        _emit(f"  Estado             {status} (código {exit_code})")
        if steps_ok:
            _emit(f"  Pasos OK           {', '.join(steps_ok)}")
        if steps_failed:
            _emit(f"  Pasos con aviso    {', '.join(steps_failed)}")

        _emit("")
        _emit("  Métricas de esta ejecución:")
        rows: list[tuple[str, object]] = [
            ("Aceptados tras puerta", ingest.get("n_puerta_ok", 0)),
            ("Rechazados (cuarentena)", ingest.get("n_cuarentena", 0)),
            ("Parquet canónicos", ingest.get("n_parquet_canonicos", 0)),
            ("Canónicos desde caché", ingest.get("n_canonical_reutilizados", 0)),
            ("Canónicos nuevos", ingest.get("n_canonical_nuevos", 0)),
            ("Errores de ingesta", ingest.get("n_error_tras_puerta", 0)),
            ("Errores de contrato (reglas)", contract_errors),
            ("Perfiles con fallo QC", n_qc_errors),
        ]
        lw = max(len(k) for k, _ in rows)
        for k, v in rows:
            _emit(f"    {k:<{lw}}  {v}")

        _emit("")
        _emit("  Anomalías (Isolation Forest) — total al 100 % del paso 02:")
        _emit(f"    Filas marcadas     {n_anomalies:,}")
        _emit("    Dónde revisarlas:")
        _emit(f"      · {self.data_dir / 'perfiles_all.ctd_anomalies.parquet'}")
        _emit(f"      · {self.data_dir}/*_ctd_anomalies.parquet  (por perfil)")
        _emit(f"      · {self.checkpoints_dir / '02_anomalies.html'}  (resumen)")
        _emit(f"      · {self.project_root / 'outputs' / 'RESUMEN_ULTIMA.html'}")

        _emit("")
        _emit("  Artefactos principales:")
        clean_all = artifacts.get("clean_all")
        if clean_all:
            _emit(f"    Visor (consolidado)  {clean_all}")
        _emit(f"    Carpeta del run      {self.data_dir}/")
        _emit(f"    Checkpoints HTML     {self.checkpoints_dir}/")
        _emit(f"    Resumen JSON         {self.run_root / 'run_summary.json'}")
        _emit(f"    Provenance           {self.run_root / 'provenance.json'}")
        if logbook_name:
            _emit(f"    Bitácora HTML        {self.run_root / logbook_name}")
        if n_quarantine:
            _emit(f"    Cuarentena (ficheros) data/quarantine/  ({n_quarantine} ficheros)")
            gr_path = self.checkpoints_dir / "00_gate_rejected_detail.json"
            if gr_path.is_file():
                _emit(f"    Detalle cuarentena   {gr_path}")
        n_ingest_fail = int(ingest.get("n_error_tras_puerta") or 0)
        if n_ingest_fail:
            if_path = self.checkpoints_dir / (
                ingest.get("ingestion_failed_detail_json") or "01_ingestion_failed_detail.json"
            )
            if if_path.is_file():
                _emit(f"    Fallos ingesta (lista) {if_path}")
        motivos = ingest.get("motivos_cuarentena") or {}
        if motivos:
            _emit("    Motivos rechazo (top 3):")
            for reason, count in sorted(motivos.items(), key=lambda x: -x[1])[:3]:
                short = reason if len(reason) <= 58 else reason[:55] + "..."
                _emit(f"      [{count}] {short}")
        
        rs_path = self.checkpoints_dir / "00_radial_skipped_detail.json"
        ru_path = self.checkpoints_dir / "00_radial_unknown_detail.json"
        if rs_path.is_file():
            _emit(f"    Omitidos (otra radial) {rs_path}")
        if ru_path.is_file():
            _emit(f"    Omitidos (sin radial)  {ru_path}")

    def section_streamlit(self) -> None:
        _section_title(5, "Visor interactivo (Streamlit)")
        _emit("  Tras el pipeline, explora series y mapa con:")
        _emit("")
        _emit("    streamlit run run/app.py")
        _emit("")
        _emit("  URL local habitual: http://localhost:8501")
        _emit("  El visor prioriza perfiles_all.ctd_clean.parquet de la última ejecución.")

    def closing_line(self, exit_code: int) -> None:
        _emit("")
        _emit("=" * _WIDTH)
        if exit_code == 0:
            _emit("  Fin del pipeline — listo para Streamlit".center(_WIDTH))
        else:
            _emit(f"  Fin del pipeline — código de salida {exit_code}".center(_WIDTH))
        _emit("=" * _WIDTH)
        _emit("")

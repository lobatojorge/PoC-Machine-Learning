"""
Cuaderno de Bitácora — IEO Orchestrator
========================================

Genera un único informe HTML por ejecución del pipeline que consolida
todos los checkpoints en un documento legible, visual y auditable.

Pensado para investigadores: sin tecnicismos innecesarios, con
indicadores visuales claros (✅ ⚠️ ❌) y esquema de flujo del pipeline.
"""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers de integridad
# ---------------------------------------------------------------------------

def _sha256_short(path: Path) -> str:
    """SHA-256 abreviado (primeros 12 caracteres) de un archivo."""
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        return h.hexdigest()[:12]
    except Exception:
        return "—"


# ---------------------------------------------------------------------------
# Lectura de checkpoints
# ---------------------------------------------------------------------------

def _load_checkpoints(checkpoints_dir: Path) -> list[dict[str, Any]]:
    """Lee todos los .metrics.json del directorio de checkpoints, ordenados."""
    steps: list[dict[str, Any]] = []
    if not checkpoints_dir.exists():
        return steps
    for p in sorted(checkpoints_dir.glob("*.metrics.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            steps.append(data)
        except Exception:
            continue
    return steps


def _load_provenance(run_root: Path) -> dict[str, Any]:
    prov_path = run_root / "provenance.json"
    if prov_path.exists():
        try:
            return json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Construcción del HTML
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --verde:   #16a34a;
  --ambar:   #d97706;
  --rojo:    #dc2626;
  --azul:    #2563eb;
  --gris:    #6b7280;
  --fondo:   #f9fafb;
  --borde:   #e5e7eb;
  --texto:   #111827;
}
* { box-sizing: border-box; }
body {
  font-family: 'Segoe UI', Arial, sans-serif;
  background: var(--fondo);
  color: var(--texto);
  margin: 0; padding: 0;
  line-height: 1.55;
}
.page { max-width: 960px; margin: 0 auto; padding: 32px 24px 64px; }

/* ── Cabecera ── */
.header {
  background: #0c1f3f;
  color: #e2e8f0;
  border-radius: 12px;
  padding: 28px 32px 24px;
  margin-bottom: 28px;
}
.header h1 { margin: 0 0 6px; font-size: 1.6rem; color: #fff; }
.header .sub { font-size: 0.85rem; color: #94a3b8; }
.header .run-id { font-family: monospace; color: #7dd3fc; font-size: 0.9rem; }

/* ── Badges de estado ── */
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.badge-ok    { background: #dcfce7; color: #15803d; }
.badge-warn  { background: #fef9c3; color: #a16207; }
.badge-error { background: #fee2e2; color: #b91c1c; }
.badge-info  { background: #dbeafe; color: #1d4ed8; }

/* ── Resumen global ── */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  margin-bottom: 28px;
}
.stat-card {
  background: #fff;
  border: 1px solid var(--borde);
  border-radius: 10px;
  padding: 16px 18px;
  text-align: center;
}
.stat-card .number { font-size: 2rem; font-weight: 700; }
.stat-card .label  { font-size: 0.8rem; color: var(--gris); margin-top: 4px; }
.stat-card.verde   .number { color: var(--verde); }
.stat-card.ambar   .number { color: var(--ambar); }
.stat-card.rojo    .number { color: var(--rojo); }
.stat-card.azul    .number { color: var(--azul); }

/* ── Diagrama de flujo ── */
.flow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  background: #fff;
  border: 1px solid var(--borde);
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 28px;
  overflow-x: auto;
}
.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 100px;
  text-align: center;
}
.flow-icon {
  font-size: 1.6rem;
  width: 52px; height: 52px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 6px;
}
.flow-icon.ok    { background: #dcfce7; }
.flow-icon.warn  { background: #fef9c3; }
.flow-icon.error { background: #fee2e2; }
.flow-icon.skip  { background: #f3f4f6; }
.flow-label { font-size: 0.72rem; color: var(--texto); font-weight: 600; line-height: 1.3; }
.flow-arrow { font-size: 1.3rem; color: #9ca3af; padding: 0 4px; margin-bottom: 20px; }

/* ── Secciones de paso ── */
.section {
  background: #fff;
  border: 1px solid var(--borde);
  border-radius: 10px;
  margin-bottom: 20px;
  overflow: hidden;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--borde);
  background: #f8fafc;
}
.section-header h2 { margin: 0; font-size: 1rem; flex: 1; }
.section-body { padding: 16px 20px; }

/* ── Tablas ── */
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th { text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--borde);
     color: var(--gris); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; }
td { padding: 7px 10px; border-bottom: 1px solid var(--borde); }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f9fafb; }

/* ── Bloques de texto ── */
.note {
  background: #eff6ff;
  border-left: 4px solid var(--azul);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 0.88rem;
  color: #1e3a5f;
  margin: 12px 0;
}
.warn-box {
  background: #fffbeb;
  border-left: 4px solid var(--ambar);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 0.88rem;
  color: #78350f;
  margin: 12px 0;
}
.error-box {
  background: #fff1f2;
  border-left: 4px solid var(--rojo);
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 0.88rem;
  color: #7f1d1d;
  margin: 12px 0;
}
code { background: #f3f4f6; padding: 2px 5px; border-radius: 4px; font-size: 0.85em; }

/* ── Firma ── */
.firma {
  background: #0c1f3f;
  color: #94a3b8;
  border-radius: 10px;
  padding: 20px 24px;
  font-size: 0.82rem;
  margin-top: 28px;
  line-height: 1.8;
}
.firma b { color: #e2e8f0; }
"""


def _badge(errors: list[str]) -> str:
    if errors:
        return '<span class="badge badge-error">❌ Error</span>'
    return '<span class="badge badge-ok">✅ Correcto</span>'


def _flow_icon_class(errors: list[str]) -> str:
    return "error" if errors else "ok"


def _flow_icon_emoji(errors: list[str]) -> str:
    return "❌" if errors else "✅"


def _human_title(step_id: str, title: str) -> str:
    """Devuelve el título más legible disponible."""
    return title if title else step_id


# Etiquetas cortas para el diagrama de flujo
_FLOW_LABELS: dict[str, tuple[str, str]] = {
    "01_ingestion":         ("🔄", "Ingesta y\nnormalización"),
    "01_ingestion_skipped": ("⏭️", "Fuente\nomitida"),
    "02_anomalies":         ("🔍", "Control\nde calidad"),
    "03_quality":           ("📊", "Resumen\nde salud"),
}


def _render_metrics_table(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "<p><i>Sin métricas registradas.</i></p>"
    rows = ""
    for k, v in sorted(metrics.items()):
        # Etiquetas más legibles para métricas comunes
        label = {
            "n_rows": "Filas totales",
            "n_rows_in": "Filas de entrada",
            "n_rows_clean": "Filas válidas",
            "n_rows_anomalies": "Filas en cuarentena",
            "n_anomalies": "Anomalías detectadas",
            "fraction_anomalies": "Proporción anómala",
            "n_features": "Variables analizadas",
            "contamination": "Sensibilidad ML (contamination)",
            "random_state": "Semilla de reproducibilidad",
            "n_sources": "Archivos de entrada",
            "n_ok": "Conversiones exitosas",
            "n_fail": "Conversiones fallidas",
            "n_casts": "Casts detectados",
            "source": "Archivo procesado",
            "audit_log_rows": "Entradas en registro de auditoría",
        }.get(str(k), str(k))

        val = v
        if isinstance(v, float):
            val = f"{v:.4f}" if abs(v) < 10 else f"{v:.2f}"
        elif isinstance(v, list):
            val = ", ".join(str(x) for x in v[:5])
            if len(v) > 5:
                val += f" … (+{len(v)-5})"

        rows += (
            f"<tr><td>{html.escape(label)}</td>"
            f"<td><code>{html.escape(str(val))}</code></td></tr>"
        )
    return f"<table><thead><tr><th>Métrica</th><th>Valor</th></tr></thead><tbody>{rows}</tbody></table>"


def _render_step(step: dict[str, Any], idx: int) -> str:
    title = html.escape(_human_title(step.get("step_id", ""), step.get("title", "")))
    errors: list[str] = step.get("errors", [])
    summary: list[str] = step.get("summary_lines", [])
    metrics: dict[str, Any] = step.get("metrics", {})
    generated = step.get("generated_at_utc", "")

    # Resumen como lista limpia
    summary_html = "".join(f"<li>{html.escape(l)}</li>" for l in summary if l.strip())
    summary_block = f"<ul style='margin:0; padding-left:18px;'>{summary_html}</ul>" if summary_html else ""

    # Errores
    if errors:
        err_items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        err_block = f'<div class="error-box"><b>Incidencias registradas:</b><ul style="margin:6px 0 0; padding-left:18px;">{err_items}</ul></div>'
    else:
        err_block = ""

    # Métricas
    metrics_block = _render_metrics_table(metrics)

    # Nota de cuarentena si procede
    quarantine_note = ""
    n_anom = metrics.get("n_rows_anomalies") or metrics.get("n_anomalies")
    if n_anom and int(n_anom) > 0:
        quarantine_note = (
            f'<div class="warn-box">⚠️ <b>{int(n_anom)} registros</b> han sido marcados como sospechosos '
            f'y enviados a cuarentena. <b>No se incluyen en los análisis</b> hasta que el investigador '
            f'los revise y confirme su exclusión o reincorporación.</div>'
        )

    ts = f'<span style="font-size:0.78rem; color:#9ca3af;">{html.escape(generated[:16].replace("T"," "))} UTC</span>' if generated else ""

    return f"""
<div class="section">
  <div class="section-header">
    <div style="font-size:1.3rem;">{"❌" if errors else "✅"}</div>
    <h2>Paso {idx} · {title}</h2>
    {_badge(errors)}
    {ts}
  </div>
  <div class="section-body">
    {summary_block}
    {quarantine_note}
    {err_block}
    <details style="margin-top:14px;">
      <summary style="cursor:pointer; font-size:0.85rem; color:#2563eb; font-weight:600;">
        Ver métricas detalladas
      </summary>
      <div style="margin-top:10px;">{metrics_block}</div>
    </details>
  </div>
</div>
"""


def _render_provenance(prov: dict[str, Any]) -> str:
    if not prov:
        return "<p><i>Información de trazabilidad no disponible.</i></p>"

    inputs = prov.get("inputs", [])
    packages = prov.get("packages", {})
    python_v = prov.get("python", "—")
    platform_v = prov.get("platform", "—")

    # Tabla de archivos de entrada
    if inputs:
        rows = ""
        for inp in inputs:
            path = inp.get("path", "—")
            sha = inp.get("sha256", "—")
            sha_short = sha[:12] + "…" if sha and sha != "—" else "—"
            size = inp.get("stat", {}).get("bytes", "—")
            size_str = f"{int(size):,} bytes" if isinstance(size, (int, float)) else str(size)
            rows += (
                f"<tr><td><code>{html.escape(Path(path).name)}</code></td>"
                f"<td><code>{html.escape(sha_short)}</code></td>"
                f"<td>{html.escape(size_str)}</td></tr>"
            )
        inputs_table = (
            "<table><thead><tr><th>Archivo</th><th>SHA-256 (abreviado)</th><th>Tamaño</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    else:
        inputs_table = "<p><i>Sin archivos de entrada registrados.</i></p>"

    # Versiones de librerías
    if packages:
        pkg_rows = "".join(
            f"<tr><td><code>{html.escape(k)}</code></td><td><code>{html.escape(v)}</code></td></tr>"
            for k, v in sorted(packages.items())
        )
        pkg_table = (
            "<table><thead><tr><th>Librería</th><th>Versión</th></tr></thead>"
            f"<tbody>{pkg_rows}</tbody></table>"
        )
    else:
        pkg_table = "<p><i>Sin información de librerías.</i></p>"

    return f"""
<div class="section">
  <div class="section-header">
    <div style="font-size:1.3rem;">🔏</div>
    <h2>Trazabilidad e integridad</h2>
    <span class="badge badge-info">Auditoría</span>
  </div>
  <div class="section-body">
    <div class="note">
      Esta sección certifica <b>qué archivos entraron</b> en el pipeline y
      <b>con qué versiones de software</b> se procesaron.
      Los códigos SHA-256 permiten verificar que los datos de entrada no han sido
      modificados después del procesado.
    </div>

    <h3 style="font-size:0.9rem; margin:16px 0 8px;">📁 Archivos de entrada</h3>
    {inputs_table}

    <h3 style="font-size:0.9rem; margin:16px 0 8px;">🐍 Entorno de ejecución</h3>
    <table>
      <tbody>
        <tr><td>Python</td><td><code>{html.escape(python_v[:60])}</code></td></tr>
        <tr><td>Sistema operativo</td><td><code>{html.escape(platform_v)}</code></td></tr>
      </tbody>
    </table>

    <h3 style="font-size:0.9rem; margin:16px 0 8px;">📦 Versiones de librerías</h3>
    {pkg_table}
  </div>
</div>
"""


def _render_flow_diagram(steps: list[dict[str, Any]]) -> str:
    """Diagrama visual del flujo del pipeline con estado de cada paso."""
    seen_ids = set()
    flow_items: list[tuple[str, str, list[str]]] = []

    for step in steps:
        sid = step.get("step_id", "")
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        emoji, label = _FLOW_LABELS.get(sid, ("🔧", sid.replace("_", " ").title()))
        errors = step.get("errors", [])
        flow_items.append((emoji, label, errors))

    if not flow_items:
        return ""

    nodes = ""
    for i, (emoji, label, errors) in enumerate(flow_items):
        cls = _flow_icon_class(errors)
        status = _flow_icon_emoji(errors)
        label_esc = html.escape(label).replace("\n", "<br>")
        nodes += f"""
        <div class="flow-step">
          <div class="flow-icon {cls}">{emoji}</div>
          <div class="flow-label">{label_esc}</div>
          <div style="font-size:0.9rem; margin-top:4px;">{status}</div>
        </div>"""
        if i < len(flow_items) - 1:
            nodes += '<div class="flow-arrow">→</div>'

    return f"""
<div class="section" style="margin-bottom:28px;">
  <div class="section-header">
    <div style="font-size:1.3rem;">🗺️</div>
    <h2>Flujo del pipeline</h2>
    <span class="badge badge-info">Resumen visual</span>
  </div>
  <div class="section-body">
    <div class="flow">{nodes}</div>
    <p style="font-size:0.8rem; color:#6b7280; margin:0;">
      ✅ Paso completado sin incidencias &nbsp;·&nbsp;
      ❌ Paso con errores &nbsp;·&nbsp;
      Los pasos con ⚠️ cuarentena requieren revisión manual antes de continuar.
    </p>
  </div>
</div>
"""


def _global_stats(steps: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    """Devuelve (n_pasos, n_ok, n_error, n_cuarentena)."""
    n_ok = sum(1 for s in steps if not s.get("errors"))
    n_err = sum(1 for s in steps if s.get("errors"))
    n_quar = 0
    for s in steps:
        m = s.get("metrics", {})
        v = m.get("n_rows_anomalies") or m.get("n_anomalies") or 0
        try:
            n_quar += int(v)
        except Exception:
            pass
    return len(steps), n_ok, n_err, n_quar


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

def write_logbook(
    *,
    run_root: Path,
    run_id: str,
    operator: str = "IEO-Orchestrator",
) -> Path:
    """
    Consolida todos los checkpoints de una ejecución en un único
    informe HTML (cuaderno de bitácora).

    Parámetros
    ----------
    run_root  : carpeta raíz de la ejecución (outputs/runs/<run_id>/)
    run_id    : identificador de la ejecución
    operator  : nombre del operador o sistema (aparece en la firma)

    Devuelve
    --------
    Path al archivo HTML generado.
    """
    checkpoints_dir = run_root / "checkpoints"
    steps = _load_checkpoints(checkpoints_dir)
    prov = _load_provenance(run_root)
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")

    n_pasos, n_ok, n_err, n_quar = _global_stats(steps)

    # Estado global
    if n_err > 0:
        estado_badge = '<span class="badge badge-error">❌ Ejecución con errores</span>'
    elif n_quar > 0:
        estado_badge = '<span class="badge badge-warn">⚠️ Revisión de cuarentena pendiente</span>'
    else:
        estado_badge = '<span class="badge badge-ok">✅ Ejecución correcta</span>'

    # Tarjetas de resumen
    summary_cards = f"""
    <div class="summary-grid">
      <div class="stat-card azul">
        <div class="number">{n_pasos}</div>
        <div class="label">Pasos ejecutados</div>
      </div>
      <div class="stat-card verde">
        <div class="number">{n_ok}</div>
        <div class="label">Pasos correctos</div>
      </div>
      <div class="stat-card rojo">
        <div class="number">{n_err}</div>
        <div class="label">Pasos con error</div>
      </div>
      <div class="stat-card ambar">
        <div class="number">{n_quar}</div>
        <div class="label">Registros en cuarentena</div>
      </div>
    </div>
    """

    # Diagrama de flujo
    flow_html = _render_flow_diagram(steps)

    # Secciones de cada paso
    steps_html = ""
    for i, step in enumerate(steps, 1):
        steps_html += _render_step(step, i)

    # Trazabilidad
    prov_html = _render_provenance(prov)

    # Firma final
    firma_html = f"""
    <div class="firma">
      <b>IEO-Orchestrator · Cuaderno de Bitácora</b><br>
      ID de ejecución: <code style="color:#7dd3fc;">{html.escape(run_id)}</code><br>
      Generado: {html.escape(now_str)}<br>
      Operador: {html.escape(operator)}<br><br>
      <span style="color:#64748b;">
        Este documento certifica de forma automática las operaciones realizadas sobre los datos
        en esta ejecución del pipeline. Los registros en cuarentena no forman parte de ningún
        análisis hasta que el investigador responsable los revise explícitamente.<br>
        Para preguntas metodológicas, consulte la documentación en <code style="color:#7dd3fc;">docs/</code>.
      </span>
    </div>
    """

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Cuaderno de Bitácora · {html.escape(run_id)}</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="page">

  <!-- CABECERA -->
  <div class="header">
    <div class="sub">Instituto Español de Oceanografía · Pipeline de Datos</div>
    <h1>📒 Cuaderno de Bitácora</h1>
    <div class="run-id">Ejecución: {html.escape(run_id)}</div>
    <div style="margin-top:10px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      {estado_badge}
      <span class="sub">{html.escape(now_str)}</span>
    </div>
  </div>

  <!-- TARJETAS DE RESUMEN -->
  {summary_cards}

  <!-- DIAGRAMA DE FLUJO -->
  {flow_html}

  <!-- NOTA METODOLÓGICA -->
  <div class="note" style="margin-bottom:24px;">
    <b>¿Qué es este documento?</b><br>
    Este informe se genera automáticamente al finalizar cada ejecución del pipeline.
    Registra <b>qué datos entraron</b>, <b>qué operaciones se realizaron</b> y
    <b>qué resultados se obtuvieron</b>, incluyendo cualquier registro marcado como sospechoso.
    Sirve como trazabilidad científica de la ejecución y puede archivarse junto a los datos procesados.
  </div>

  <!-- PASOS DEL PIPELINE -->
  <h2 style="font-size:1rem; color:#374151; margin:0 0 14px; text-transform:uppercase;
             letter-spacing:0.05em;">Detalle por paso</h2>
  {steps_html}

  <!-- TRAZABILIDAD -->
  {prov_html}

  <!-- FIRMA -->
  {firma_html}

</div>
</body>
</html>
"""

    out_path = run_root / f"logbook_{run_id}.html"
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path

"""
Resumen visual único de la última ejecución del pipeline.

Genera:
- ``outputs/RESUMEN_ULTIMA.html`` (informe en navegador)
- ``outputs/LEEME_RESUMEN.txt`` (ruta al HTML; el HTML está en .gitignore)
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from ieo.radial_labels import label_es

_EXIT_LABELS: dict[int, tuple[str, str]] = {
    0: ("ok", "Ejecución completada correctamente"),
    1: ("warn", "Ejecución terminada con errores (ingesta, contrato o anomalías)"),
    2: ("warn", "No se encontraron ficheros .cnv de entrada"),
    3: ("bad", "Todos los ficheros fueron rechazados en el control previo (cuarentena)"),
}


def _esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def _filtro_ingesta_legible(filtro: str) -> str:
    if filtro == "todas":
        return "Todas las radiales (pipeline completo; por defecto)"
    return f"{label_es(filtro)} — alcance `IEO_PIPELINE_RADIAL={filtro}`"


def _filtro_ingesta_corto(filtro: str) -> str:
    if filtro == "todas":
        return "Todas las radiales"
    return label_es(filtro)


def format_ingest_console(ingest: dict[str, Any]) -> str:
    """Resumen multilínea para consola: inventario por ciudad y cifras de la ejecución."""
    filtro = str(ingest.get("filtro_radial", "todas"))
    lines: list[str] = ["", "  --- Inventario data/cnv (por ciudad) ---"]

    inv = ingest.get("inventario_por_radial") or {}
    if inv:
        w = max((len(label_es(rid)) for rid in inv), default=8)
        for rid, count in sorted(inv.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"    {label_es(rid):<{w}}  {count:>5}")
        if ingest.get("inventario_total"):
            lines.append(f"    {'TOTAL':<{w}}  {ingest['inventario_total']:>5}")
    else:
        lines.append("    (sin desglose por radial)")

    lines.append("")
    lines.append("  --- Esta ejecución ---")
    rows: list[tuple[str, object]] = [
        ("Alcance", _filtro_ingesta_corto(filtro)),
        ("Evaluados (control previo)", ingest.get("n_cudillero_candidatos", 0)),
        ("Fuera de alcance (en disco)", ingest.get("n_omitidas_otra_radial", 0)),
        ("Aceptados -> ingesta", ingest.get("n_puerta_ok", 0)),
        ("Rechazados -> cuarentena", ingest.get("n_cuarentena", 0)),
        ("Parquet canónicos", ingest.get("n_parquet_canonicos", 0)),
        ("Canónicos reutilizados (caché)", ingest.get("n_canonical_reutilizados", 0)),
        ("Canónicos nuevos (ingesta)", ingest.get("n_canonical_nuevos", 0)),
        ("QC restaurado desde caché", ingest.get("n_qc_desde_cache", 0)),
        ("Errores al generar Parquet", ingest.get("n_error_tras_puerta", 0)),
        ("Copias a data/checked/", ingest.get("copias_a_data_checked", 0)),
    ]
    label_w = max(len(k) for k, _ in rows)
    for k, v in rows:
        lines.append(f"    {k:<{label_w}}  {v}")

    n_ny = int(ingest.get("n_cnv_non_year_shards") or 0)
    if n_ny > 0:
        ny = ingest.get("cnv_non_year_shard_counts") or {}
        parts = ", ".join(f"{k}={v}" for k, v in sorted(ny.items(), key=lambda x: -x[1])[:6])
        lines.append(f"    Lotes sin carpeta AAAA  {n_ny} ({parts})")

    omitidas = ingest.get("omitidas_por_radial") or {}
    if omitidas and filtro != "todas":
        lines.append("    Omitidos (otras ciudades):")
        for rid, count in sorted(omitidas.items(), key=lambda x: -x[1])[:8]:
            lines.append(f"      {label_es(rid):<14}  {count:>5}")

    motivos = ingest.get("motivos_cuarentena") or {}
    if motivos:
        lines.append("")
        lines.append("  --- Motivos de rechazo (conteo) ---")
        for reason, count in sorted(motivos.items(), key=lambda x: -x[1])[:8]:
            short = reason if len(reason) <= 72 else reason[:69] + "..."
            lines.append(f"    [{count:>4}]  {short}")

    n_des = sum(
        1
        for x in (ingest.get("muestra_omitidas_radial") or [])
        if str(x.get("radial")) == "desconocida"
    )
    if n_des:
        lines.append(f"    Sin clasificar (radial)  {n_des}  (detalle en HTML/checkpoints)")

    nota = ingest.get("nota_data_checked")
    if nota and str(nota).strip():
        lines.append(f"    Nota  {str(nota).strip()}")
    lines.append("")
    return "\n".join(lines)


def format_run_footer(
    *,
    run_id: str,
    exit_code: int,
    steps_ok: list[str],
    steps_failed: list[str],
    n_anomalies: int,
    contract_errors: int,
    n_quarantine: int,
    artifacts: dict[str, str],
) -> str:
    """Pie compacto tras terminar el pipeline."""
    status = {0: "OK", 1: "con avisos", 2: "sin .cnv", 3: "todo rechazado"}.get(exit_code, "?")
    lines = [
        "",
        "  --- Resultado ---",
        f"    Run ID              {run_id}",
        f"    Estado              {status} (código {exit_code})",
    ]
    if steps_ok:
        lines.append(f"    Pasos OK            {', '.join(steps_ok)}")
    if steps_failed:
        lines.append(f"    Pasos con error     {', '.join(steps_failed)}")
    lines.append(f"    Anomalías (IF)      {n_anomalies}")
    lines.append(f"    Errores contrato    {contract_errors}")
    if n_quarantine:
        lines.append(f"    En cuarentena       {n_quarantine}  (data/quarantine/)")
    if artifacts.get("clean_all"):
        lines.append(f"    Parquet consolidado perfiles_all.ctd_clean.parquet")
    lines.append("")
    return "\n".join(lines)


def _ingest_html_block(ingest: dict[str, Any]) -> str:
    inv = ingest.get("inventario_por_radial") or {}
    inv_html = ""
    if inv:
        inv_rows = "".join(
            f"<tr><td>{_esc(label_es(rid))} <span class='muted'>({_esc(rid)})</span></td>"
            f"<td><code>{_esc(count)}</code></td></tr>"
            for rid, count in sorted(inv.items(), key=lambda x: (-x[1], x[0]))
        )
        inv_html = (
            "<h3>Inventario completo en carpeta (por radial)</h3>"
            "<table><thead><tr><th>Radial</th><th>Ficheros</th></tr></thead><tbody>"
            f"{inv_rows}</tbody></table>"
        )

    ny_html = ""
    n_ny = int(ingest.get("n_cnv_non_year_shards") or 0)
    if n_ny > 0:
        ny = ingest.get("cnv_non_year_shard_counts") or {}
        ny_bits = ", ".join(
            f"{_esc(k)}=<code>{_esc(v)}</code>" for k, v in sorted(ny.items(), key=lambda x: -x[1])[:12]
        )
        ny_html = (
            "<h3>Lotes sin carpeta-año (primer segmento ≠ <code>AAAA</code>)</h3>"
            f"<p><strong>{_esc(n_ny)}</strong> ficheros .cnv — {ny_bits}. "
            "Preflight: <code>python run/preflight_cnv.py</code></p>"
        )

    pfs = ingest.get("cnv_preflight_summary")
    pf_html = ""
    if isinstance(pfs, dict) and pfs.get("questions"):
        q_items = "".join(f"<li>{_esc(q)}</li>" for q in pfs["questions"][:8])
        pf_html = (
            "<h3>Preguntas automáticas (<code>IEO_CNV_PREFLIGHT=1</code>)</h3>"
            f"<ol>{q_items}</ol>"
        )

    filtro = str(ingest.get("filtro_radial", "todas"))
    pipe_rows = [
        ("Alcance del pipeline", _filtro_ingesta_legible(filtro)),
        ("Evaluados (control previo)", ingest.get("n_cudillero_candidatos", 0)),
        ("No evaluados en esta ejecución (siguen en disco; visor puede abrirlos)", ingest.get("n_omitidas_otra_radial", 0)),
        ("Aceptados → ingesta", ingest.get("n_puerta_ok", 0)),
        ("Rechazados → cuarentena", ingest.get("n_cuarentena", 0)),
        ("Parquet generados", ingest.get("n_parquet_canonicos", 0)),
        ("Errores al generar Parquet", ingest.get("n_error_tras_puerta", 0)),
        ("Copias a data/checked/", ingest.get("copias_a_data_checked", 0)),
    ]
    tbody = "".join(
        f"<tr><td>{_esc(k)}</td><td><code>{_esc(v)}</code></td></tr>" for k, v in pipe_rows
    )

    omitidas = ingest.get("omitidas_por_radial") or {}
    omitidas_html = ""
    if omitidas and ingest.get("filtro_radial") != "todas":
        omitidas_html = (
            "<h3>Omitidos en esta ejecución (alcance <code>IEO_PIPELINE_RADIAL</code>)</h3>"
            "<p class='muted'>Siguen en <code>data/cnv/</code>; el visor multi-radial puede abrirlos. "
            "Aquí solo se lista el conteo por radial.</p><ul>"
        )
        for rid, count in sorted(omitidas.items(), key=lambda x: -x[1])[:12]:
            omitidas_html += (
                f"<li><strong>{count}</strong> — {_esc(label_es(rid))} "
                f"<span class='muted'>({_esc(rid)})</span></li>"
            )
        omitidas_html += "</ul>"

    muestra_des = [
        x
        for x in (ingest.get("muestra_omitidas_radial") or [])
        if str(x.get("radial")) == "desconocida"
    ][:15]
    des_html = ""
    if muestra_des:
        des_html = (
            "<h3>Muestra sin clasificar (cruise en cabecera)</h3>"
            "<table><thead><tr><th>Ruta bajo data/cnv</th><th>Cruise (truncado)</th></tr></thead><tbody>"
        )
        for item in muestra_des:
            rel = _esc(item.get("rel") or item.get("file", "?"))
            ch = item.get("cruise_hint") or ""
            des_html += f"<tr><td><code>{rel}</code></td><td>{_esc(ch[:200])}</td></tr>"
        des_html += "</tbody></table>"

    motivos = ingest.get("motivos_cuarentena") or {}
    motivos_html = ""
    if motivos:
        motivos_html = "<h3>Motivos de cuarentena (conteo)</h3><ul>"
        for reason, count in sorted(motivos.items(), key=lambda x: -x[1])[:15]:
            motivos_html += f"<li><strong>{count}</strong> — {_esc(reason)}</li>"
        motivos_html += "</ul>"
    motivos_ing = ingest.get("motivos_error_ingesta") or {}
    ingest_fail_html = ""
    if motivos_ing:
        detail_name = ingest.get("ingestion_failed_detail_json") or "01_ingestion_failed_detail.json"
        ingest_fail_html = (
            "<h3>Errores de ingesta tras puerta (sin copia a cuarentena)</h3>"
            f"<p class='muted'>El `.cnv` sigue en <code>data/cnv/</code>. "
            f"Listado completo en <code>checkpoints/{_esc(detail_name)}</code>.</p><ul>"
        )
        for reason, count in sorted(motivos_ing.items(), key=lambda x: -x[1])[:15]:
            ingest_fail_html += f"<li><strong>{count}</strong> — {_esc(reason)}</li>"
        ingest_fail_html += "</ul>"
    muestra = ingest.get("muestra_cuarentena") or []
    muestra_html = ""
    if muestra:
        muestra_html = (
            "<h3>Ejemplos rechazados (control previo)</h3>"
            "<table><thead><tr><th>Fichero</th><th>Motivo</th></tr></thead><tbody>"
        )
        for item in muestra[:25]:
            rs = "; ".join(item.get("reasons") or [])
            fn = item.get("file_label") or item.get("file", "?")
            muestra_html += f"<tr><td><code>{_esc(fn)}</code></td><td>{_esc(rs)}</td></tr>"
        muestra_html += "</tbody></table>"
    nota = ingest.get("nota_data_checked", "")
    return (
        f"<h2>Ingesta de ficheros .cnv</h2>"
        f"<p class='muted'>«Control previo» = comprobaciones automáticas antes de ingestar (ingest_gate); "
        f"si no se cumplen → cuarentena en <code>data/quarantine/</code>.</p>"
        f"{inv_html}{ny_html}{pf_html}"
        f"<h3>Esta ejecución del pipeline</h3><table><tbody>{tbody}</tbody></table>"
        f"<p class='muted'>{_esc(nota)}</p>{des_html}{omitidas_html}{motivos_html}"
        f"{ingest_fail_html}{muestra_html}"
    )


def write_resumen_ultima_html(
    *,
    project_root: Path,
    run_root: Path,
    summary: dict[str, Any],
) -> Path:
    """Genera HTML + puntero LEEME en ``outputs/``."""
    out_dir = project_root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "RESUMEN_ULTIMA.html"

    run_id = summary.get("run_id", "?")
    exit_code = int(summary.get("exit_code", -1))
    badge_class, status_text = _EXIT_LABELS.get(
        exit_code,
        ("unk", f"Código de salida desconocido: {exit_code}"),
    )

    rel_run = Path("runs") / run_root.name
    ingest = summary.get("ingest") or {}
    ingest_html = _ingest_html_block(ingest)
    fatal = summary.get("fatal_error")
    fatal_html = ""
    if fatal:
        tb = ""
        if isinstance(ingest, dict):
            tb = str(ingest.get("fatal_pipeline_traceback") or "")
        fatal_html = (
            "<h2>Error fatal</h2>"
            f"<p><code>{_esc(fatal)}</code></p>"
        )
        if tb:
            fatal_html += (
                "<h3>Trazado (recorte)</h3>"
                f"<pre style='white-space:pre-wrap;font-size:0.75rem;background:#fef2f2;"
                f"padding:12px;border-radius:6px'>{_esc(tb[-8000:])}</pre>"
            )
    steps_ok = summary.get("steps_ok") or []
    steps_fail = summary.get("steps_failed") or []
    artifacts = summary.get("artifacts") or {}
    gen = summary.get("generated_at_utc", "?")

    art_rows = ""
    for k, v in artifacts.items():
        art_rows += f"<tr><td><code>{_esc(k)}</code></td><td><code>{_esc(v)}</code></td></tr>"
    if not art_rows:
        art_rows = "<tr><td colspan='2'>Sin artefactos Parquet en esta ejecución</td></tr>"

    steps_ok_html = (
        "<ul>" + "".join(f"<li><code>{_esc(s)}</code></li>" for s in steps_ok) + "</ul>"
        if steps_ok else "<p>Ninguno.</p>"
    )
    steps_fail_html = (
        "<ul>" + "".join(f"<li><code>{_esc(s)}</code></li>" for s in steps_fail) + "</ul>"
        if steps_fail else "<p>Ninguno.</p>"
    )

    css = """
    body { font-family: system-ui, Segoe UI, sans-serif; margin: 0; background: #f4f4f5; color: #18181b; }
    .wrap { max-width: 920px; margin: 0 auto; padding: 28px 20px 48px; }
    h1 { font-size: 1.35rem; margin: 0 0 8px; }
    h2 { font-size: 1.05rem; margin: 28px 0 10px; border-bottom: 1px solid #e4e4e7; padding-bottom: 6px; }
    h3 { font-size: 0.95rem; margin: 16px 0 8px; }
    .badge { display: inline-block; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; }
    .ok { background: #dcfce7; color: #166534; }
    .warn { background: #fef9c3; color: #854d0e; }
    .bad { background: #fee2e2; color: #991b1b; }
    .unk { background: #e4e4e7; color: #3f3f46; }
    table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.06); margin-bottom: 12px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #f4f4f5; font-size: 0.88rem; }
    th { background: #fafafa; font-weight: 600; }
    code { font-size: 0.82rem; word-break: break-all; }
    ul { margin: 8px 0; padding-left: 1.2rem; }
    .links a { margin-right: 14px; }
    .muted { color: #71717a; font-size: 0.85rem; margin-top: 8px; }
    """

    body = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Resumen última ejecución — {_esc(run_id)}</title>
  <style>{css}</style>
</head>
<body>
  <div class="wrap">
    <h1>Resumen de la última ejecución del pipeline</h1>
    <p class="muted">Generado automáticamente. Se sobrescribe en cada <code>python run/main.py</code>.</p>
    <p><span class="badge {badge_class}">{_esc(status_text)}</span></p>
    <p><strong>Run ID</strong>: <code>{_esc(run_id)}</code> &nbsp;·&nbsp; <strong>Código</strong>: <code>{exit_code}</code><br/>
    <strong>UTC</strong>: <code>{_esc(gen)}</code></p>
    <p class="links">
      <a href="{_esc((rel_run / 'run_summary.json').as_posix())}">run_summary.json</a>
      <a href="{_esc((rel_run / 'provenance.json').as_posix())}">provenance.json</a>
      <a href="{_esc((rel_run / 'checkpoints').as_posix())}/">checkpoints/</a>
    </p>

    {fatal_html}
    {ingest_html}

    <h2>Métricas de calidad</h2>
    <table><tbody>
      <tr><td>Anomalías (Isolation Forest)</td><td><code>{_esc(summary.get('n_anomalies', 0))}</code></td></tr>
      <tr><td>Errores de contrato (ERROR)</td><td><code>{_esc(summary.get('contract_errors', 0))}</code></td></tr>
    </tbody></table>

    <h2>Pasos correctos</h2>{steps_ok_html}
    <h2>Pasos fallidos</h2>{steps_fail_html}
    <h2>Artefactos</h2>
    <table><thead><tr><th>Tipo</th><th>Ruta</th></tr></thead><tbody>{art_rows}</tbody></table>
    <p class="muted">Carpeta de salida (run): <code>{_esc(run_root)}</code></p>
  </div>
</body>
</html>"""

    out_path.write_text(body, encoding="utf-8")

    leeme = out_dir / "LEEME_RESUMEN.txt"
    leeme.write_text(
        "Resumen visual de la última ejecución del pipeline\n"
        "================================================\n\n"
        f"Abre en el navegador (doble clic):\n  {out_path.resolve()}\n\n"
        "Este fichero sí está en el repositorio; el HTML está en .gitignore "
        "porque depende de tus datos locales.\n\n"
        f"Última ejecución: {run_root.name}\n",
        encoding="utf-8",
    )
    return out_path

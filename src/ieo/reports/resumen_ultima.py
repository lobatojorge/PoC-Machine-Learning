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

_EXIT_LABELS: dict[int, tuple[str, str]] = {
    0: ("ok", "Ejecución completada correctamente"),
    1: ("warn", "Ejecución terminada con errores (ingesta, contrato o anomalías)"),
    2: ("warn", "No se encontraron ficheros .cnv de entrada"),
    3: ("bad", "Todos los ficheros fueron rechazados por la puerta de cuarentena"),
}


def _esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def format_ingest_console(ingest: dict[str, Any]) -> str:
    """Texto multilínea para consola."""
    lines = [
        "  --- Ingesta .cnv ---",
        f"  Filtro activo                : {ingest.get('filtro_radial', 'cudillero')}",
        f"  Encontrados en data/cnv/     : {ingest.get('n_cnv_encontrados', 0)}",
        f"  Candidatos Cudillero         : {ingest.get('n_cudillero_candidatos', 0)}",
        f"  Omitidos (otras radiales)    : {ingest.get('n_omitidas_otra_radial', 0)}",
        f"  Pasaron la puerta            : {ingest.get('n_puerta_ok', 0)}",
        f"  Cuarentena                   : {ingest.get('n_cuarentena', 0)}",
        f"  Parquet canónico generados   : {ingest.get('n_parquet_canonicos', 0)}",
        f"  Error tras la puerta         : {ingest.get('n_error_tras_puerta', 0)}",
        f"  Copias a data/checked/       : {ingest.get('copias_a_data_checked', 0)}",
    ]
    omitidas = ingest.get("omitidas_por_radial") or {}
    if omitidas:
        lines.append("  Omitidos por radial (conteo):")
        for rid, count in sorted(omitidas.items(), key=lambda x: -x[1])[:6]:
            lines.append(f"    · {rid}: {count}")
    motivos = ingest.get("motivos_cuarentena") or {}
    if motivos:
        lines.append("  Motivos cuarentena (resumen):")
        for reason, count in sorted(motivos.items(), key=lambda x: -x[1])[:8]:
            short = reason if len(reason) <= 90 else reason[:87] + "…"
            lines.append(f"    · [{count}] {short}")
    muestra = ingest.get("muestra_cuarentena") or []
    if muestra:
        lines.append("  Ejemplos rechazados:")
        for item in muestra[:5]:
            name = item.get("file", "?")
            rs = item.get("reasons") or []
            r0 = rs[0] if rs else "?"
            if len(r0) > 80:
                r0 = r0[:77] + "…"
            lines.append(f"    · {name}: {r0}")
    nota = ingest.get("nota_data_checked")
    if nota:
        lines.append(f"  Nota: {nota}")
    return "\n".join(lines)


def _ingest_html_block(ingest: dict[str, Any]) -> str:
    rows = [
        ("Filtro radial", ingest.get("filtro_radial", "cudillero")),
        ("Ficheros .cnv en data/cnv/", ingest.get("n_cnv_encontrados", 0)),
        ("Candidatos Cudillero", ingest.get("n_cudillero_candidatos", 0)),
        ("Omitidos (otras radiales)", ingest.get("n_omitidas_otra_radial", 0)),
        ("Pasaron la puerta", ingest.get("n_puerta_ok", 0)),
        ("Enviados a cuarentena", ingest.get("n_cuarentena", 0)),
        ("Parquet canónico generados", ingest.get("n_parquet_canonicos", 0)),
        ("Errores tras la puerta", ingest.get("n_error_tras_puerta", 0)),
        ("Copias a data/checked/", ingest.get("copias_a_data_checked", 0)),
    ]
    tbody = "".join(
        f"<tr><td>{_esc(k)}</td><td><code>{_esc(v)}</code></td></tr>" for k, v in rows
    )
    omitidas = ingest.get("omitidas_por_radial") or {}
    omitidas_html = ""
    if omitidas:
        omitidas_html = "<h3>Omitidos por radial (no Cudillero)</h3><ul>"
        for rid, count in sorted(omitidas.items(), key=lambda x: -x[1])[:12]:
            omitidas_html += f"<li><strong>{count}</strong> — {_esc(rid)}</li>"
        omitidas_html += "</ul>"
    motivos = ingest.get("motivos_cuarentena") or {}
    motivos_html = ""
    if motivos:
        motivos_html = "<h3>Motivos de cuarentena (conteo)</h3><ul>"
        for reason, count in sorted(motivos.items(), key=lambda x: -x[1])[:15]:
            motivos_html += f"<li><strong>{count}</strong> — {_esc(reason)}</li>"
        motivos_html += "</ul>"
    muestra = ingest.get("muestra_cuarentena") or []
    muestra_html = ""
    if muestra:
        muestra_html = "<h3>Ejemplos rechazados</h3><table><thead><tr><th>Fichero</th><th>Motivo</th></tr></thead><tbody>"
        for item in muestra[:25]:
            rs = "; ".join(item.get("reasons") or [])
            muestra_html += f"<tr><td><code>{_esc(item.get('file', '?'))}</code></td><td>{_esc(rs)}</td></tr>"
        muestra_html += "</tbody></table>"
    nota = ingest.get("nota_data_checked", "")
    return (
        f"<h2>Ingesta de ficheros .cnv</h2><table><tbody>{tbody}</tbody></table>"
        f"<p class='muted'>{_esc(nota)}</p>{omitidas_html}{motivos_html}{muestra_html}"
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

    steps_ok = summary.get("steps_ok") or []
    steps_fail = summary.get("steps_failed") or []
    artifacts = summary.get("artifacts") or {}
    quarantine = summary.get("quarantine") or []
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

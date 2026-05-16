from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StepReport:
    """
    Reporte simple de un paso del pipeline.

    Explicación práctica
    --------------------
    Un reporte es “una página” que cuenta:
    - qué se intentó hacer
    - qué salió bien
    - qué salió mal (si algo falló)
    - y números clave del dataset
    """

    step_id: str
    title: str
    summary_lines: list[str]
    metrics: dict[str, Any]
    errors: list[str]


def write_step_report(
    *,
    out_dir: Path,
    report: StepReport,
) -> tuple[Path, Path]:
    """
    Escribe dos archivos por paso:
    - `<step_id>.html`
    - `<step_id>.metrics.json`
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{report.step_id}.html"
    json_path = out_dir / f"{report.step_id}.metrics.json"

    json_path.write_text(
        json.dumps(
            {
                "step_id": report.step_id,
                "title": report.title,
                "metrics": report.metrics,
                "errors": report.errors,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary_html = "".join(f"<li>{html.escape(line)}</li>" for line in report.summary_lines)
    errors_html = (
        "<ul>" + "".join(f"<li><b>{html.escape(e)}</b></li>" for e in report.errors) + "</ul>"
        if report.errors
        else "<p><i>Sin errores reportados.</i></p>"
    )

    metrics_rows = []
    for k, v in sorted(report.metrics.items(), key=lambda kv: str(kv[0])):
        metrics_rows.append(
            f"<tr><td style='padding:6px; border-bottom:1px solid #e5e7eb;'><code>{html.escape(str(k))}</code></td>"
            f"<td style='padding:6px; border-bottom:1px solid #e5e7eb;'>{html.escape(str(v))}</td></tr>"
        )
    metrics_html = (
        "<table style='border-collapse:collapse; width:100%;'>"
        "<thead><tr>"
        "<th style='text-align:left; border-bottom:2px solid #111827; padding:6px;'>Métrica</th>"
        "<th style='text-align:left; border-bottom:2px solid #111827; padding:6px;'>Valor</th>"
        "</tr></thead><tbody>"
        + "".join(metrics_rows)
        + "</tbody></table>"
        if metrics_rows
        else "<p><i>Sin métricas.</i></p>"
    )

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(report.title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; line-height: 1.45; color: #111827; }}
    h1 {{ margin: 0 0 8px 0; }}
    code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
    .muted {{ color: #6b7280; }}
    .box {{ border:1px solid #e5e7eb; border-radius:8px; padding:12px; margin: 12px 0; }}
  </style>
</head>
<body>
  <p class="muted">Reporte generado: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</p>
  <h1>{html.escape(report.title)}</h1>

  <div class="box">
    <h2 style="margin-top:0;">Qué se ha hecho</h2>
    <ul>{summary_html}</ul>
  </div>

  <div class="box">
    <h2 style="margin-top:0;">Métricas</h2>
    {metrics_html}
  </div>

  <div class="box">
    <h2 style="margin-top:0;">Qué ha fallado</h2>
    {errors_html}
  </div>

  <p class="muted">Archivo de métricas: <code>{html.escape(json_path.name)}</code></p>
</body>
</html>
"""

    html_path.write_text(html_doc, encoding="utf-8")
    return html_path, json_path


from __future__ import annotations

"""
Registro público de ejecuciones (auditoría legible).

Objetivo
--------
Un único fichero Markdown, apendizable, que documente *qué se ha puesto en marcha*
y *qué limitaciones tiene* el análisis, sin pretender sustituir el juicio de un
estadístico ni la revisión externa (p. ej. en R).

No sustituye trazabilidad fina del pipeline (JSON/provenance por ``run_id``),
pero sí da una pista humana continua para quien abre el proyecto sin contexto.
"""

import importlib.util
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_FILE_REL = Path("outputs") / "audit" / "registro_ejecuciones.md"
_PATHS_MOD = "_ieo_repo_paths_audit"


def _default_radial_csv_path(project_root: Path) -> Path:
    """Misma lógica que `ieo.paths` sin `import ieo.*` (Streamlit / pip homónimo)."""
    if _PATHS_MOD not in sys.modules:
        cp = Path(__file__).resolve().parents[1] / "paths.py"
        spec = importlib.util.spec_from_file_location(_PATHS_MOD, cp)
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError(f"No se encuentra {cp}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_PATHS_MOD] = mod
        spec.loader.exec_module(mod)
    return sys.modules[_PATHS_MOD].default_radial_csv_path(project_root)


def _radial_csv_exists(project_root: Path) -> bool:
    return _default_radial_csv_path(project_root).is_file()


def append_public_run_journal_entry(
    project_root: Path,
    *,
    kind: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """
    Añade una entrada al diario ``outputs/audit/registro_ejecuciones.md``.

    Parameters
    ----------
    kind
        Identificador corto, p. ej. ``streamlit_dashboard_boot`` o ``pipeline_cli``.
    extra
        Pares clave-valor opcionales (se listan como viñetas).
    """
    path = project_root / AUDIT_FILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    iso = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    has_csv = _radial_csv_exists(project_root)

    lines: list[str] = [
        "---",
        f"## Entrada · {iso}",
        "",
        f"- **Tipo de ejecución:** `{kind}`",
        f"- **Python:** `{sys.version.split()[0]}` · **Plataforma:** `{platform.platform()}`",
        f"- **CSV radial Cudillero (`data/checked/perfiles_all.csv`):** **{'presente' if has_csv else 'ausente'}**",
        "",
        "### Transparencia (lectura para investigación)",
        "",
        "- Las gráficas son **herramientas de exploración**; una figura clara **no implica** que el fenómeno sea simple ni que el modelo sea el único válido.",
        "- El bloque tipo **Marcos + ATAC** (visualización) usa **tendencia + estacionalidad mensual**; el error se modela como **ruido blanco gaussiano** sobre residuos (sin autocorrelación). Con **pocos meses** o muchos huecos, los resultados pueden ser **inestables o no ajustables**.",
        "- Los ficheros `.cnv` en `data/cnv/` se clasifican por **coordenadas** y metadatos; `RCAN` indica campaña Cantábrico, no una radial fija.",
        "- La **T a 5 m** depende de que el perfil **abraque 5 m**; si no, ese mes puede quedar vacío aunque el CTD tenga buena calidad en otras profundidades.",
        "- Ficheros en `data/raw/` (p. ej. `.cnv`) son **solo respaldo** y no entran al pipeline ni al visor salvo copia explícita al CSV de trabajo.",
        "",
        "### Qué no registra este fichero",
        "",
        "- **Cursor / agentes de IA:** no queda aquí un “log de cada clic del agente”. El editor puede guardar **transcripciones de chat** en su carpeta de proyecto; eso es independiente de este repositorio y **no equivale** a un libro de laboratorio firmado.",
        "- **Reproducibilidad tipo R:** si su laboratorio valida en R, conviene **fijar semillas**, versionar paquetes (`renv` / `sessionInfo()`), y comparar salidas numéricas con las tablas intermedias del pipeline (`outputs/runs/...`) cuando existan.",
        "",
        "### Recomendación mínima ante un revisor escéptico",
        "",
        "- Pedir **n**, rango temporal, % de meses faltantes, y sensibilidad al **holdout**.",
        "- Comparar con un análisis **paralelo en R** sobre los mismos datos agregados (misma definición de T a 5 m).",
        "",
    ]
    if extra:
        lines.append("### Detalles adicionales")
        lines.append("")
        for k, v in extra.items():
            lines.append(f"- **{k}:** `{v}`")
        lines.append("")

    text = "\n".join(lines) + "\n"
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="\n") as f:
        if new_file:
            f.write(
                "# Registro público de ejecuciones (IEO)\n\n"
                "Este fichero se **va ampliando** al final: cada bloque corresponde a un arranque "
                "del visor Streamlit o del orquestador `run/main.py`. "
                "Sirve como memoria humana y como recordatorio de limitaciones; **no** sustituye "
                "un informe firmado, un control de calidad estadístico ni la trazabilidad fina "
                "del pipeline (véase `outputs/runs/<run_id>/` cuando aplique).\n\n"
            )
        f.write(text)
    return path

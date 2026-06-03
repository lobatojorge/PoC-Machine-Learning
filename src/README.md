# Carpeta `src/` — Código activo

## Paquete principal: `src/ieo/`

Todo el código del pipeline de producción.

| Subcarpeta / módulo | Responsabilidad |
|---------------------|-----------------|
| `ieo/io/` | Lectores: CnvReader (`.cnv` SeaBird), `cnv_radial.py` (clasificación por lat/lon + metadatos), Excel, NetCDF. |
| `ieo/viz/load_radial_cnv_profiles.py` | Carga exploratoria de `.cnv` por `radial_id` (visor); asegura columna `estacion` desde cabecera cuando falta. |
| `ieo/reports/radial_cnv_geo.py` | Índice geográfico (medianas lat/lon por radial) para el mapa del visor. |
| `ieo/reports/monthly_at_depth.py` | Serie mensual a profundidad fija; un CTD/mes = lance **más profundo**. |
| `ieo/reports/plot_gaps.py` | Utilidades Plotly por tramos (visor ATAC usa marcadores sin unir huecos). |
| `ieo/transform/` | Esquema normalizado y construcción del LazyFrame de referencia. |
| `ieo/validation/` | Contratos de calidad: `radial_contract.py` (reglas CTD Cantábrico) y `generic_series_contract.py` (capa reutilizable). |
| `ieo/observability/` | Isolation Forest (`contamination=0.05`, `random_state=42`), resumen de salud, auditoría de sesión. |
| `ieo/runtime/` | Rutas por corrida (`run_id`), provenance, bitácora. |
| `ieo/reports/` | Informes HTML por paso, `resumen_ultima.py` (RESUMEN_ULTIMA.html), `console_run.py` (salida estructurada en consola), bitácora y figuras Plotly (`figures_radiales.py`). |
| `ieo/pipeline_cache.py` | Manifiesto incremental (`pipeline_manifest.json`) y caché de Parquet entre ejecuciones. |
| `ieo/pipeline_qc.py` | Paso 02 en paralelo: contrato + Isolation Forest por perfil (`contamination=0.05`). |
| `ieo/ingest_gate.py` | Control previo (antes de ingestar): evalúa cada `.cnv` seleccionado y envía a cuarentena si no cumple reglas mínimas. |
| `ieo/cli.py` | Orquesta todos los pasos del pipeline. Entrada: `run_pipeline()`. |
| `ieo/cudillero_paths.py` | Rutas de datos: `cnv_dir()`, `checked_dir()` (y helpers legacy). |
| `ieo/cnv_layout.py` | Detecta lotes bajo `data/cnv/` sin convención de carpeta-año (`AAAA/`). |
| `ieo/cnv_preflight.py` | Inventario + preguntas + dubios para carpetas nuevas (puerta + radial). |
| `ieo/radial_labels.py` | Nombres en español de `radial_id` para consola y `RESUMEN_ULTIMA.html`. |
| `ieo/pipeline_env.py` | Resolución de `IEO_PIPELINE_RADIAL` y compatibilidad con variables legacy. |

## Módulos ATAC (visor)

| Archivo | Responsabilidad |
|---------|-----------------|
| `02_analysis.py` | Marcos (tendencia + Fourier), bandas iid sobre residuos (**sin AR**). |
| `atac_monthly_report.py` | Figura mensual + holdout 1 mes; marcadores (sin polilíneas). Usada por `run/app.py`. |

## Flujo de dependencias

```
run/main.py
    └─► ieo/cli.py
            ├─► ieo/cudillero_paths.py  (data/cnv/ recursivo)
            ├─► ieo/pipeline_env.py      (alcance IEO_PIPELINE_RADIAL / legacy)
            ├─► ieo/io/cnv_radial.py    (paso 00a · filtro por alcance, si aplica)
            ├─► ieo/ingest_gate.py      (paso 00b · control previo / cuarentena por fichero)
            ├─► ieo/io/cnv_reader.py    (paso 01 · lee .cnv SeaBird)
            ├─► ieo/transform/          (paso 01 · normalización)
            ├─► ieo/validation/         (paso 01b · contrato)
            ├─► ieo/observability/      (paso 02 · anomalías)
            └─► ieo/reports/            (checkpoints HTML + run_summary.json + RESUMEN_ULTIMA.html)

run/app.py (Streamlit)
    ├─► ieo/reports/figures_radiales.py  (mapa, coords)
    ├─► ieo/reports/radial_cnv_geo.py    (índice ciudades/estaciones desde data/cnv/)
    ├─► ieo/viz/load_radial_cnv_profiles.py  (CNV → pandas por radial)
    └─► src/atac_monthly_report.py       (Marcos + ATAC)
            └─► src/02_analysis.py
```

> El código de Streamlit (CSS, caché, lógica de UI) permanece en `run/app.py`.
> Las funciones Plotly reutilizables sin Streamlit están en `ieo/reports/figures_radiales.py`.

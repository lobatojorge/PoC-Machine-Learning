# Carpeta `src/` — Código activo

## Paquete principal: `src/ieo/`

Todo el código del pipeline de producción.

| Subcarpeta / módulo | Responsabilidad |
|---------------------|-----------------|
| `ieo/io/` | Lectores: CnvReader (`.cnv` SeaBird), `cnv_radial.py` (clasificación por lat/lon + metadatos), Excel, NetCDF. |
| `ieo/reports/plot_gaps.py` | Trazos Plotly solo entre meses consecutivos. |
| `ieo/transform/` | Esquema normalizado y construcción del LazyFrame de referencia. |
| `ieo/validation/` | Contratos de calidad: `radial_contract.py` (reglas CTD Cantábrico) y `generic_series_contract.py` (capa reutilizable). |
| `ieo/observability/` | Isolation Forest, resumen de salud, auditoría de sesión. |
| `ieo/runtime/` | Rutas por corrida (`run_id`), provenance, bitácora. |
| `ieo/reports/` | Informes HTML por paso, `resumen_ultima.py` (RESUMEN_ULTIMA.html), bitácora y figuras Plotly (`figures_radiales.py`). |
| `ieo/ingest_gate.py` | Puerta de cuarentena: evalúa cada `.cnv` **Cudillero** antes de ingestarlo. |
| `ieo/cli.py` | Orquesta todos los pasos del pipeline. Entrada: `run_pipeline()`. |
| `ieo/cudillero_paths.py` | Rutas de datos: `cnv_dir()`, `checked_dir()` (y helpers legacy). |
| `ieo/radiales_catalog.py` | Catálogo de estaciones y filtro por radial (Cudillero). |

## Módulos ATAC (visor)

| Archivo | Responsabilidad |
|---------|-----------------|
| `02_analysis.py` | Marcos (tendencia + Fourier), bandas iid sobre residuos (**sin AR**). |
| `atac_monthly_report.py` | Figura mensual + holdout; visualización tipo ATAC. Usada por `run/app.py`. |

## Flujo de dependencias

```
run/main.py
    └─► ieo/cli.py
            ├─► ieo/cudillero_paths.py  (data/cnv/ recursivo)
            ├─► ieo/io/cnv_radial.py    (paso 00a · solo Cudillero)
            ├─► ieo/ingest_gate.py      (paso 00b · cuarentena por fichero)
            ├─► ieo/io/cnv_reader.py    (paso 01 · lee .cnv SeaBird)
            ├─► ieo/transform/          (paso 01 · normalización)
            ├─► ieo/validation/         (paso 01b · contrato)
            ├─► ieo/observability/      (paso 02 · anomalías)
            └─► ieo/reports/            (checkpoints HTML + run_summary.json + RESUMEN_ULTIMA.html)

run/app.py (Streamlit)
    ├─► ieo/reports/figures_radiales.py  (mapa, coords)
    └─► src/atac_monthly_report.py       (Marcos + ATAC)
            └─► src/02_analysis.py
```

> El código de Streamlit (CSS, caché, lógica de UI) permanece en `run/app.py`.
> Las funciones Plotly reutilizables sin Streamlit están en `ieo/reports/figures_radiales.py`.

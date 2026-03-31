<!-- AUTO-START -->
# PEC2 — Informe de Seguimiento

## Resumen ejecutivo

En esta fase he consolidado el esqueleto operativo del proyecto como un sistema reproducible: pipeline de ingesta/validación, capa de visualización y auditoría de datos. El objetivo ha sido sentar una base robusta y trazable para convertir datos oceanográficos heterogéneos en productos analíticos interpretables.

## Relación de las actividades realizadas

He desarrollado y orquestado componentes del flujo de trabajo en `src/` para cubrir:
- reconocimiento/triage de datos y cuarentena (Human-in-the-Loop)
- normalización de columnas y validación de contrato CTD
- productos de visualización orientados a serie temporal y estructura vertical

En paralelo, he documentado metodología y trazabilidad en `docs/` y he creado outputs exportables para uso en informes.

## Estado del repositorio (auditoría)

> 🤖 [AUTO-GENERADO: Estado del Repositorio]

- **Fecha de auditoría**: 2026-03-18 13:22:56
- **Scripts en `src/`**: 14
  - `src\00_data_scout.py`
  - `src\00_ingestion.py`
  - `src\00_router.py`
  - `src\01_agent_inspector.py`
  - `src\02_analysis.py`
  - `src\02_pec_generator.py`
  - `src\03_visualization\visualizador_atac.py`
  - `src\03_visualization.py`
  - `src\__init__.py`
  - `src\agents\agent_curator.py`
  - `src\agents\agent_inspector.py`
  - `src\fig_export.py`
  - `src\prueba.py`
  - `src\visualization.py`
- **Docs Markdown en `docs/`**: 8
  - `docs\metodologia_otros.md`
  - `docs\metodologia_radiales_gijon.md`
  - `docs\metodologia_radiales_vigo.md`
  - `docs\PEC\PEC2_Informe.md`
  - `docs\PEC\PEC3_Informe.md`
  - `docs\PEC\PEC4_Memoria_Esqueleto.md`
  - `docs\PEC\PEC5_Storyboard.md`
  - `docs\recon_global.md`
- **Tamaño `docs/recon_global.md`**: 16.2 KB

- **Puntos de progreso (heurístico)**: 111/100
  - Encontrado enrutador `src/00_router.py` (+40).
  - Encontrada interfaz `app.py` (+40).
  - Scripts en `src/`: 13 (bonificación aplicada).
  - Docs `.md` en `docs/`: 8 (bonificación aplicada).
  - Ficheros en `data/`: 31 (bonificación aplicada).

## Evidencias técnicas generadas

He producido figuras exportables (PNG) orientadas a comunicación de resultados y verificación:
- `outputs/figures/` contiene gráficos listos para adjuntar (serie T(5 m), Hovmöller, etc.).
- `docs/recon_global.md` registra el triage automático y casos en cuarentena.

## Riesgos y plan de mitigación

- **Riesgo: sesgo por esfuerzo de muestreo** (años/estaciones con diferente densidad de perfiles).
  - *Mitigación*: reportar `n` por año/estación, usar IC global pool total y anotar limitaciones.
- **Riesgo: heterogeneidad y errores de formato en datos crudos**.
  - *Mitigación*: contrato CTD + cuarentena HitL + registro de razones en `recon_global.md`.
- **Riesgo: fragilidad de exportación de figuras (dependencia de motor de imagen)**.
  - *Mitigación*: fijar dependencia (Kaleido/Chrome) y smoke test de exportación.
<!-- AUTO-END -->

## Notas y ajustes manuales (no se sobrescribe)

<!-- HUMAN-START -->
Puedes escribir aquí observaciones personales, decisiones no capturadas por el repo, y cambios que quieras introducir antes de entregar. Este bloque se conserva cuando se re-ejecuta el generador.
<!-- HUMAN-END -->

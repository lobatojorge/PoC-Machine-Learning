<!-- AUTO-START -->
# PEC4 — Memoria (Esqueleto)

## Resumen

Este documento recoge la memoria técnica del TFM: motivación, metodología, arquitectura, resultados y conclusiones. La aproximación se plantea como un sistema de ingeniería de datos para observaciones oceanográficas con control de calidad, observabilidad y visualización.

## Metodología (Enfoque Ingeniería de Datos)

### Arquitectura Medallón
- **Bronce**: ingesta cruda (preservación, trazabilidad, auditoría).
- **Plata**: limpieza/normalización, contratos de datos, control de calidad.
- **Oro**: productos analíticos y visualización (KPIs, series, Hovmöller).

### Contratos de Datos y Observabilidad (Data Observability)
- Definir variables mínimas y rangos plausibles.
- Validaciones automáticas (filas mínimas, amplitud vertical, columnas CTD).
- Registro de cuarentena y razones (auditabilidad).

### Patrón Human-in-the-Loop (HitL)
- Automatizar el triaje y **detener**/cuarentenar cuando hay ambigüedad.
- Forzar revisión humana en casos de alta incertidumbre o mezcla de dominios.

### Conexión con Competencias
- **CE10**: Identificación de requerimientos informáticos (contratos, validaciones, pipeline reproducible).
- **CE14**: Integración de conocimientos bioinformáticos (datos oceanográficos + criterios de calidad + visualización).

## Arquitectura del Sistema

La arquitectura se organiza como un pipeline por etapas con outputs rastreables y auditoría:
- scripts numerados para reflejar el orden lógico
- validación de contrato CTD y cuarentena
- capa de visualización con exportación de figuras para informes

## Resultados

Los resultados se expresan como productos reproducibles:
- series temporales interpretables (p. ej. T(5 m) anual)
- mapas Hovmöller para estructura vertical
- reportes de triage y calidad de datos

## Conclusiones

La contribución principal es un marco reproducible y auditable que conecta calidad de datos con productos de visualización útiles para análisis oceanográfico, manteniendo trazabilidad y control de incertidumbre.
<!-- AUTO-END -->

## Notas y ajustes manuales (no se sobrescribe)

<!-- HUMAN-START -->
Puedes escribir aquí observaciones personales, decisiones no capturadas por el repo, y cambios que quieras introducir antes de entregar. Este bloque se conserva cuando se re-ejecuta el generador.
<!-- HUMAN-END -->

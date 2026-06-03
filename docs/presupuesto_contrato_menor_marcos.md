# Propuesta - Contrato menor (<15.000 EUR) - Asistencia tecnica "Auditoria visual de datos CTD"

Cliente: **Marcos (IP)**  
Objetivo: **reducir tiempo perdido** por el equipo en limpiar basura, ficheros corruptos y anomalias **antes** de modelar/publicar.

---

## Que entregamos (en lenguaje de Marcos)

Un **panel visual** (tipo "cuadro de mando") que, tras arrastrar/copiar los ficheros de campana, te responde en minutos:

- **Que ficheros entran** y cuales se rechazan "en la puerta" (y por que).
- Que datos quedan **listos para analisis** y que parte queda marcada como **sospechosa** (sin borrarla).
- Un **informe de ejecucion** legible para justificar decisiones y repetir el proceso sin discusiones internas.

---

## Modulos (entregables cerrados y presupuestables)

### 1) Filtro Antibasura (control previo con informe)
- **Analogia**: "Un antivirus para los ficheros de campana: lo roto no entra al analisis".
- **Entregable**: ejecucion que separa automaticamente "apto / no apto", con listado completo de rechazados y motivo.
- **Impacto cientifico**: evita que el equipo invierta horas en ficheros inviables; acelera el paso a modelos/publicacion.
- **Componentes del repo**:
  - `src/ieo/ingest_gate.py`
  - `src/ieo/io/cnv_header.py`
  - `src/ieo/cli.py` (paso 00 + reportes)
  - `src/ieo/reports/html_report.py`

### 2) Auditoria de ejecucion (embudo + trazabilidad)
- **Analogia**: "Un parte de campana: cuantos entraron, cuantos quedaron utiles, que se perdio y donde".
- **Entregable**: informe en una sola pagina (mas checklists) para revision/justificacion.
- **Impacto cientifico**: reproducibilidad y justificacion rapida en memorias y auditorias internas.
- **Componentes del repo**:
  - `scripts/audit_report.py`
  - `src/ieo/reports/resumen_ultima.py`
  - `src/ieo/reports/logbook.py`
  - `src/ieo/runtime/provenance.py`

### 3) Revisor visual de datos sospechosos (panel Streamlit)
- **Analogia**: "Un radar que marca mediciones improbables para que tu equipo revise rapido sin borrar nada".
- **Entregable**: panel Streamlit para explorar datos limpios vs sospechosos con narrativa para no tecnicos. Isolation Forest con `contamination=0.05` (5 % por estrato).
- **Impacto cientifico**: reduce el riesgo de contaminar series con outliers; acelera datasets "publicables".
- **Componentes del repo**:
  - `run/app.py`
  - `run/viewer_presentation.py`
  - `src/ieo/pipeline_qc.py`
  - `src/ieo/observability/anomaly.py`
  - `src/ieo/validation/radial_contract.py`

---

## Instalacion/operacion (lo minimo que Marcos necesita saber)

- **Entrada**: copiar ficheros `.cnv` a `data/cnv/`.
- **Ejecucion**: `python run/main.py` (genera artefactos y resumen) y `streamlit run run/app.py` (panel).
- **Salida**: un resumen visual y un panel para revisar.

---

## Exclusiones (para mantener el contrato menor)

- No incluye integraci�n con infra IEO/servidores corporativos (se puede cotizar aparte).
- No incluye migracion masiva historica ni limpieza manual "uno a uno" de campanas.
- No incluye soporte 24/7; si una ventana de acompanamiento acordada.


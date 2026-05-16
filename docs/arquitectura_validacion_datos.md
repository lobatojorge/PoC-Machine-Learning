# Arquitectura de validación y auditoría de datos

Patrón genérico implementado en IEO Orchestrator y demostrado en la radial de **Cudillero**. Pensado para reutilizarse en otras campañas (p. ej. series temporales en volcanología, sensores ambientales, otros transectos costeros).

---

## Principio

Separar cuatro responsabilidades que suelen mezclarse en un único script o en un dashboard:

1. **Transformar** datos crudos a un esquema canónico.
2. **Validar** contra reglas de dominio (contrato).
3. **Detectar** valores atípicos sin borrarlos (observabilidad).
4. **Analizar y visualizar** solo sobre salidas trazables.

---

## Diagrama de capas

```mermaid
flowchart TB
  subgraph ingest [1_Ingesta]
    RAW[Fuentes_crudas_CSV_CNV]
    READ[Readers_pluggables]
    CAN[Esquema_canonico]
    RAW --> READ --> CAN
  end

  subgraph prov [2_Provenance]
    RUN[run_id]
    META[provenance_json]
    RUN --> META
  end

  subgraph qc [3_Contrato_de_datos]
    VAL[Reglas_ERROR_WARNING]
    RPT[Informes_checkpoint]
    CAN --> VAL --> RPT
  end

  subgraph obs [4_Observabilidad]
    IF[Deteccion_anomalias]
    CLEAN[Dataset_limpio]
    ANOM[Dataset_anomalias]
    CAN --> IF
    IF --> CLEAN
    IF --> ANOM
  end

  subgraph anal [5_Analisis_validado]
    SER[Serie_temporal_agregada]
    MOD[Modelo_Marcos_ATAC]
    HOLD[Holdout_y_bandas]
    CLEAN --> SER --> MOD --> HOLD
  end

  subgraph ui [6_Visor_gobernado]
    CARDS[Tarjetas_QC]
    CHART[Grafica_interactiva]
    FAQ[Contexto_FAQ_avisos]
    CLEAN --> CARDS
    HOLD --> CHART
    VAL --> FAQ
  end

  ingest --> prov
  prov --> qc
  qc --> obs
  obs --> anal
  anal --> ui
```

---

## Capas en detalle

### 1. Ingesta canónica

- **Entrada:** archivos heterogéneos (CSV, futuro `.cnv`, Excel legacy).
- **Salida:** tabla con columnas fijas (fecha, estación, profundidad, variables).
- **Código:** `src/ieo/io/`, `src/ieo/transform/canonical_schema.py`, `src/ieo/transform/pipeline.py`.

### 2. Provenance

- Cada ejecución del pipeline genera un `run_id` y metadatos (`provenance.json`).
- Permite reproducir qué fuente y parámetros produjeron cada figura del visor.
- **Código:** `src/ieo/runtime/run_id.py`, `src/ieo/runtime/provenance.py`.

### 3. Contrato de datos

- Reglas declarativas en Python con severidad **ERROR** (bloquea gráfica en visor) y **WARNING** (contexto tras interpretar).
- No sustituye el juicio científico; formaliza umbrales acordados.
- **Código:** `src/ieo/validation/radial_contract.py` · **Doc:** `docs/contrato_datos_radiales.md`.

### 4. Observabilidad

- Isolation Forest multivariante (T, S, profundidad) con semilla fija.
- Filas anómalas en Parquet separado; trazables en informes HTML.
- **Código:** `src/ieo/observability/anomaly.py`, paso 02 del pipeline.

### 5. Análisis con validación

- Serie mensual por estación y profundidad objetivo.
- Descomposición estacional + pronóstico AR con bandas; holdout explícito (últimos N meses).
- **Código:** `src/02_analysis.py`, `src/atac_monthly_report.py`.

### 6. Visor gobernado

- Consume Parquet de la corrida seleccionada, no el CSV crudo.
- Tarjetas de calidad, hitos, preguntas frecuentes, avisos de contrato en lenguaje claro.
- **Código:** `run/app.py`.

---

## Interfaz del contrato (desacoplada del visor)

Conceptualmente:

```
entrada: DataFrame | LazyFrame canónico
salida:  list[Violation]  # code, severity, message, details
```

El visor y el pipeline comparten las mismas funciones; Streamlit solo renderiza `Violation` ya formateadas. Esto permite reutilizar el contrato en CLI, tests (`scripts/e2e_smoke.py`) o, en el futuro, otro frontend web.

---

## Catálogo de dominio (plantilla)

`src/ieo/radiales_catalog.py` identifica estaciones y filtra por radial (Cudillero vs Santander, etc.). El mismo patrón sirve para un **catálogo de sensores o estaciones volcánicas**: códigos permitidos, metadatos, reglas de rechazo temprano en ingesta.

---

## Caso demostrado vs producto genérico

| Aspecto | Genérico (arquitectura) | Demo actual (Cudillero) |
|---------|-------------------------|-------------------------|
| Esquema canónico | Sí | CTD radial |
| Contrato | Sí | T, S, serie mensual, saltos verticales |
| Visor | Sí | T/S @ 5 m, 3 estaciones |
| Despliegue | Diseño | Streamlit local / URL demo |

---

## Referencias

- TRL y roadmap: [`posicionamiento_trl.md`](posicionamiento_trl.md)
- Integración web IEO: [`integracion_web_ieo.md`](integracion_web_ieo.md)

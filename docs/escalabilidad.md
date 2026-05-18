# Objetivos de escalabilidad — IEO Orchestrator

Hoja de ruta técnica para cuando el sistema crezca más allá del TRL 4 actual.
Cada punto está anotado con su motivación y los riesgos principales.

---

## 1. Lector CNV nativo

**Estado:** implementado (versión inicial).  
**Módulo:** `src/ieo/io/cnv_reader.py`

El técnico vuelca ficheros `.cnv` (SeaBird) en `data/cnv/`. El pipeline los detecta
automáticamente y los procesa sin conversión manual previa.

**Cómo funciona ahora:**
- `_detect_sources()` en `cli.py` escanea `data/cnv/*.cnv`.
- `CnvReader.read()` parsea la cabecera SeaBird (`# name N = varname: …`) y los datos
  espacio-separados tras `*END*`.
- La puerta de cuarentena (`ingest_gate.py`) reconoce `.cnv` y extrae columnas para
  verificar presencia de temperatura, profundidad y fecha.
- `provenance.json` registra el SHA256 del fichero `.cnv` original para trazabilidad.

**Parche temporal (demo):**  
`data/csv/` acepta ficheros `.csv` tabulares. `CnvReader` delega en `RadialCsvReader`
cuando detecta la extensión `.csv`. Este parche se eliminará cuando el flujo CNV sea
operativo en producción.

**Pendiente:**
- Cobertura de variantes de cabecera (SBE19, SBE25, CTD911).
- Columna temporal por fila cuando el `.cnv` incluye `timeJ` (días julianos).
- Tests de integración con ficheros `.cnv` reales del IEO.

---

## 2. Flujo de agentes sobre CNV

**Estado:** parcialmente implementado.  
**Flujo actual:**
```
data/cnv/*.cnv  ──► ingest_gate ──► (OK) ──► pipeline → outputs/
data/csv/*.csv  ──► ingest_gate ──► (OK) ──► pipeline → outputs/  [demo]
                                └─► (KO) ──► data/quarantine/
```

**Pendiente para producción:**
1. Acumulación de múltiples `.cnv` en un único Parquet de referencia.
2. Materializar el CSV normalizado en `data/checked/` como respaldo intermedio.
3. Notificación automática al técnico si un fichero va a cuarentena.

---

## 3. TimeGPT / PatchTST / modelos profundos de series

**Estado:** pendiente de requisito científico validado.  
**Motivación:** el bloque Marcos + ATAC actual usa descomposición mensual clásica +
AR(1). Modelos como **TimeGPT** (Nixtla) o **PatchTST** (transformer para series)
pueden capturar patrones no lineales y correlaciones cruzadas entre estaciones
si hay suficientes datos.

**Cuándo tiene sentido:**
- Series con ≥ 20 años de datos mensuales sin huecos grandes.
- Se quiere pronóstico multivariante (T y S simultáneos) o entre estaciones.
- El investigador acepta un modelo "caja negra" parcial con validación holdout
  explícita.

**Cuándo NO tiene sentido:**
- Series cortas o con muchos huecos (el modelo no converge bien).
- El objetivo es solo detectar anomalías (Isolation Forest + contrato ya cubre esto).
- Se requiere interpretabilidad total para publicación científica.

**Riesgo principal:** coste computacional, dependencia de API externa (TimeGPT)
o GPU local (PatchTST), y opacidad del modelo sin métricas de validación claras.

**Próximo paso cuando proceda:** experimento acotado en notebook con holdout
extendido (últimos 24 meses) y comparación RMSE contra el baseline Marcos+AR(1).

---

## 4. Migración del contrato a Great Expectations (GX)

**Estado:** pendiente; solo si TI institucional lo requiere.  
**Motivación:** el contrato actual (`radial_contract.py`) es código Python propio
con severidades ERROR/WARNING. Great Expectations ofrece suites declarativas,
documentación HTML automática e integración con catálogos de datos.

**Cuándo tiene sentido:** integración institucional con Alation, OpenMetadata u
otro catálogo de datos donde el contrato deba ser legible por perfiles no técnicos.

**Coste:** rediseño del contrato como suite GX + integración en CI. No urgente
para TRL 4-5.

---

## 5. Portal web IEO (sustitución de Streamlit)

**Estado:** ver `docs/integracion_web_ieo.md`.  
**Motivación:** Streamlit es un demostrador ágil. Para integración en la web
institucional del IEO, las funciones de gráficas están ya desacopladas del
framework en `src/ieo/reports/figures_radiales.py` y pueden consumirse desde
cualquier backend (FastAPI + React, Dash, etc.) sin reescribir la lógica de
visualización.

**Dependencias previas:** autenticación, acuerdo TI, embargo de campaña.

---

## 6. Salida JSON estructurada del pipeline (implementado)

El pipeline ya escribe `outputs/runs/<run_id>/run_summary.json` con código de
salida, pasos OK/fallidos, recuentos de anomalías y errores de contrato, y rutas
de artefactos. `run/main.py` lo lee y lo muestra en consola.

**Extensión futura:** webhook o notificación automática (email, Slack) cuando
el pipeline termina, usando el JSON como payload.

---

## 7. Orquestación programada

**Estado:** pipeline lanzado manualmente.  
**Extensión prevista:** cron / Airflow / GitHub Actions scheduled para corridas
periódicas automáticas cuando los datos CNV lleguen por FTP o carpeta compartida.

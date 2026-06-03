# IEO Orchestrator — Radiales Cantábrico (pipeline + visor)

[![CI](https://github.com/lobatojorge/IEO-Orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/lobatojorge/IEO-Orchestrator/actions/workflows/ci.yml)

## Qué es esto

Un **sistema de auditoría de datos oceanográficos** con tres componentes:

1. **Pipeline reproducible** (`run/main.py`): control previo (comprobaciones + cuarentena) → ingesta `.cnv` → contrato de calidad → segregación de anomalías (Isolation Forest) → Parquet versionado con `provenance.json`, `run_summary.json` y **`outputs/RESUMEN_ULTIMA.html`**. Por defecto la **misma** cadena aplica a **todas** las radiales en `data/cnv/`. El alcance se puede acotar con **`IEO_PIPELINE_RADIAL=<id>`** (`cudillero`, `gijon`, `santander`, `coruna`, `vigo`) para menos CPU; **`IEO_ONLY_CUDILLERO=1`** equivale a `IEO_PIPELINE_RADIAL=cudillero`. Si la corrida aborta por excepción no capturada, el resumen HTML se escribe igualmente con sección **Error fatal**.
2. **Contrato de datos en código** (`src/ieo/validation/`): reglas con severidad ERROR/WARNING versionadas en git y verificadas en CI — no en un documento PDF.
3. **Visor gobernado** (`run/app.py`): demo **priorizada en Gijón** (hero + embudo de pasos narrados en `viewer_presentation.py`), mapas Cantábrico y transecto como **contexto visual**, selección principal de estación por **botones**, series T/S @ 5 m con Marcos + bandas. Si hay corrida con Parquet bajo `outputs/runs/`, el visor la usa **filtrando por radial** también para **Gijón**; si falta corrida útil cae a `.cnv` clasificados. **Holdout del último mes**, marcadores sin unir huecos de campaña; varios CTD en un mismo mes → **lance más profundo**. Detalle y orden de carga: [`docs/visor_radiales.md`](docs/visor_radiales.md).

La arquitectura es transferible a otros dominios: datos volcánicos, calidad de agua, cualquier serie temporal de sensor. Ver [`docs/arquitectura_validacion_datos.md`](docs/arquitectura_validacion_datos.md) y [`docs/domain_catalog.md`](docs/domain_catalog.md).

**TRL actual: 4** — pipeline multi-radial + demo reproducible (presentación priorizada en Gijón). Limitaciones clasificadas (financiación vs metodología vs alcance TFM): [`docs/posicionamiento_trl.md`](docs/posicionamiento_trl.md).

---

## Demo rápida → [`DEMO.md`](DEMO.md)

Pipeline sobre ficheros **SeaBird `.cnv`** y visor **Streamlit** (Marcos + bandas tipo ATAC) para **radiales Cantábrico**. El visor lee los **Parquet** de la última corrida cuando el esquema es compatible (conjunto multi-radial en disco) y aplica **`radial_id=gijon`** en la demo de pantalla única para filtrado y series rápidas.

**Modelo en el visor:** tendencia + estacionalidad mensual (Marcos); incertidumbre = residuos **iid gaussianos** (σ constante, **sin AR**). Pronóstico sobre el **último mes con observación** (excluido del ajuste). Puntos de observación y ajuste como **marcadores** (sin polilíneas entre campañas).

**Auditoría de clasificación radial en disco:** `python run/audit_cnv_radials.py` → `outputs/temporal/cnv_radial_audit.csv` (generado localmente; no versionado).

---

## Carpetas de datos

| Ubicación | Uso |
|-----------|-----|
| `data/cnv/` | **Entrada en disco:** `.cnv` de todas las radiales. Por defecto el pipeline aplica la **misma** cadena a todas. Alcance opcional: `IEO_PIPELINE_RADIAL=cudillero|gijon|santander|coruna|vigo`. Compatibilidad: `IEO_ONLY_CUDILLERO=1` (= `cudillero`). El visor prioriza Parquet de `outputs/runs/` cuando la corrida es válida (incl. filtrado a la radial de la demo, hoy **Gijón**). |
| `data/quarantine/` | `.cnv` rechazados en el **control previo** + `reasons.json`. |
| `data/processed/` | **Legacy** (CSV Sireno Excel/Gijón, si existiera en tu copia local). **No** la crea el pipeline CNV actual ni es obligatoria para auditar `.cnv`. |
| `outputs/runs/<run_id>/data/*.parquet` | **Salida del pipeline** y **entrada del visor** (multi-radial): `*_ctd_clean.parquet`, `*_ctd_anomalies.parquet`, `perfiles_all.ctd_clean.parquet`, etc. El visor filtra por `radial_id`. |
| `outputs/temporal/radial_geo_index.cache.json` | **Caché local** del índice geo del visor (invalidada por huella del árbol `data/cnv/**/*.cnv`). Generado al vuelo; no versionado. |
| `outputs/RESUMEN_ULTIMA.html` | **Resumen visual** de la última ejecución de `run/main.py` (se sobrescribe siempre, incluso si la corrida termina en error fatal). |
| `outputs/pipeline_manifest.json` | Índice incremental (SHA256 por `.cnv`); no versionado. |
| `outputs/artifact_cache/` | Parquet canónicos y QC reutilizables entre ejecuciones; no versionado. |

> **Trazabilidad:** `outputs/runs/<run_id>/provenance.json` registra el SHA256 de cada fichero fuente,
> la versión de Python, la plataforma y los parámetros de la corrida. Los ficheros `.hex` y `.xmlcon`
> originales del CTD se conservan en la base de datos del buque; el SHA256 del `.cnv` exportado
> es suficiente para rastrear la cadena de custodia.

Las carpetas `data/*` (salvo `.gitkeep`) y la mayoría de `outputs/*` están en **`.gitignore`**.

---

## Arranque rápido

Orden: **primero** el pipeline (genera Parquet), **después** el visor.

```bash
# 1. Instalar dependencias (una sola vez)
pip install -r run/requirements.txt

# 2. Coloca los .cnv en data/cnv/ (mezcla de radiales OK; el pipeline ingiere todas por defecto)

# 3. Ejecutar el pipeline (incremental por defecto: solo .cnv nuevos o modificados)
python run/main.py           # consola: datos → pasos → progreso → resultados → Streamlit
# Reconstrucción completa:  $env:IEO_FULL_REBUILD = "1"  (PowerShell)

# 4. Abrir el resumen visual (opcional)
#    outputs/RESUMEN_ULTIMA.html en el navegador

# 5. Lanzar el visor
streamlit run run/app.py     # → demo radial Gijón (E1GI–E4GI); ejecutar después del pipeline para ir por Parquet
```

**Docker (opcional):** ver [`docs/operacion_tfm.md`](docs/operacion_tfm.md).

---

## Alcance radial del pipeline

En `data/cnv/` suelen convivir casts de **Gijón, Santander, Vigo, A Coruña y Cudillero**.
Cada `.cnv` trae la radial en metadatos SeaBird, sobre todo:

| Metadato | Ejemplo |
|----------|---------|
| `** Cruise:` | `Radial Santander`, `Radial Gijón`, …; `RCAN_*` / `Radiales Cantábrico` = **campaña**, no radial |
| `** Latitude/Longitude:` | **Principal** para asignar radial si el cruise es ambiguo |
| `** Station:` | Número de estación del cast (E2SA, E2GI, …) |
| Nombre fichero | `gjul101.cnv` → Gijón; prefijo `s` → Santander; `jul301.cnv` sin prefijo → Cudillero (si no hay coords) |

Por defecto el pipeline **evalúa e ingiere todas** las radiales clasificables (mismo control previo, Parquet, contrato e Isolation Forest). La salida (`run_summary.json`, consola, `RESUMEN_ULTIMA.html`) incluye **inventario por ciudad/radial** y el detalle de la corrida.

- Acotar una radial (menos CPU): `IEO_PIPELINE_RADIAL=gijon python run/main.py` (ids: `cudillero`, `gijon`, `santander`, `coruna`, `vigo`).
- Compatibilidad: `IEO_ONLY_CUDILLERO=1` equivale a `IEO_PIPELINE_RADIAL=cudillero`.
- `IEO_ALL_RADIALS=1` es redundante con el valor por defecto (se avisa en consola).
- Límite de prueba: `IEO_MAX_CNV=10 python run/main.py`
- Contrato de **años** en columna `fecha` (paso 01b y QC del visor con Parquet): `IEO_SAMPLING_YEAR_MIN`, `IEO_SAMPLING_YEAR_MAX` (enteros; ver [`docs/contrato_datos_radiales.md`](docs/contrato_datos_radiales.md)).

Clasificación en `src/ieo/io/cnv_radial.py` (geo → cruise explícito → nombre). La regla geográfica de **A Coruña** usa Galicia occidental (`lon` ≤ −7° aprox.), no el Cantábrico central, para no confundir aguas al norte de Gijón con la radial coruñesa.

La clasificación vive en `src/ieo/io/cnv_radial.py`.

---

## Flujo del pipeline

```
data/cnv/**/*.cnv   (todas las radiales en disco)
                  │
                  ▼ Paso 00a: (opcional) acotar radial con IEO_PIPELINE_RADIAL / legacy IEO_ONLY_CUDILLERO
                  │
                  ▼ Paso 00b: control previo / cuarentena (ingest_gate.py)
                  │   ─ si falla → data/quarantine/<ts>_fichero + reasons.json
                  │   ─ SHA256 registrado en provenance.json
                  │
                  ▼ Paso 01: ingesta y normalización (CnvReader + ieo/transform/)
                  │   ─ escribe <stem>.ctd_canonical.parquet
                  │
                  ▼ Paso 01b: contrato radial (ieo/validation/)
                  │   ─ ERROR / WARNING por fila; informe HTML en checkpoints/
                  │
                  ▼ Paso 02: Isolation Forest (ieo/observability/anomaly.py)
                  │   ─ escribe *_ctd_clean.parquet, *_ctd_anomalies.parquet, *_ctd_anomaly_audit.parquet
                  │
                  ▼ Paso 03: resumen de calidad (ieo/observability/quality_summary.py)
                  │   ─ informe HTML legible para no técnicos
                  │
                  ▼ Cierre: provenance.json + bitácora + run_summary.json + outputs/RESUMEN_ULTIMA.html
```

**Isolation Forest** no sustituye el contrato radial: el contrato aplica **reglas físicas por fila** (rangos, saltos); el IF detecta **combinaciones estadísticamente inusuales** en el conjunto completo. Son capas complementarias. El IF usa **`contamination=0.05`** (5 % de filas atípicas esperadas por estrato) y se estratifica por radial y profundidad para evitar sesgos entre radiales.

**Cuarentena de ficheros** vs **segregación de filas**: el **control previo** (paso 00b, `ingest_gate`) actúa sobre el fichero entero antes de tocarlo. El IF actúa sobre las filas ya cargadas. Son niveles distintos de control.

---

## Resumen visual de la última corrida

Tras **cada** ejecución de `python run/main.py` (éxito o error), el pipeline genera o actualiza:

**`outputs/RESUMEN_ULTIMA.html`**

- Una sola página, fácil de leer en el navegador.
- Incluye estado de la corrida, pasos OK/fallidos, métricas rápidas, enlaces relativos a `run_summary.json`, `provenance.json` y la carpeta `checkpoints/` de esa corrida.
- **Se sobrescribe** en cada ejecución (no acumula historial; el historial sigue en `outputs/runs/<run_id>/`).
- Está en **`.gitignore`** para no versionar datos locales.

La consola también imprime la ruta al final cuando el fichero existe.

---

## Contrato mínimo de una corrida

Tras un `python run/main.py` exitoso, bajo `outputs/runs/<run_id>/`:

| Ruta relativa | Rol |
|---------------|-----|
| `provenance.json` | Fuentes y parámetros al inicio de la corrida. |
| `run_summary.json` | Resumen estructurado: código de salida, pasos, artefactos, conteo de anomalías y errores. |
| `data/<stem>.ctd_canonical.parquet` | Tabla normalizada (todas las filas) por fichero fuente. |
| `data/<stem>.ctd_clean.parquet` | Filas no marcadas como anomalía. |
| `data/<stem>.ctd_anomalies.parquet` | Filas anómalas (no eliminadas). |
| `data/<stem>.ctd_anomaly_audit.parquet` | Registro del modelo de anomalías. |
| `checkpoints/*.html` | Informes HTML legibles por paso. |

---

## Estructura relevante

```text
├── data/
│   ├── cnv/                        # entrada: .cnv (subcarpetas por año OK)
│   └── quarantine/                 # .cnv rechazados en el control previo
├── docs/
│   ├── escalabilidad.md            # roadmap técnico (TimeGPT, CNV, GX, web)
│   ├── arquitectura_validacion_datos.md
│   ├── posicionamiento_trl.md
│   └── ...
├── src/
│   ├── README.md                   # mapa de src/
│   ├── ieo/                        # pipeline completo
│   ├── 02_analysis.py              # Marcos + bandas iid (sin AR)
│   └── atac_monthly_report.py      # figura mensual para el visor
├── run/
│   ├── main.py                     # lanzador del pipeline
│   ├── app.py                      # visor Streamlit
│   ├── audit_cnv_radials.py        # auditoría de clasificación radial en data/cnv/
│   └── requirements.txt
├── tests/                          # pytest (fixtures sintéticos, sin datos reales)
└── outputs/
    ├── RESUMEN_ULTIMA.html         # resumen visual última corrida (gitignored)
    └── runs/                       # artefactos por run_id (gitignored)
```

---

## Stack

Python 3.11+, Polars (pipeline), Pandas + Plotly (visor Streamlit), scikit-learn (Isolation Forest).

**Validación:** contrato propio en `src/ieo/validation/`:
- `radial_contract.py` — reglas CTD Cantábrico (temperatura, **salinidad con gradiente vertical**, saltos mes-a-mes con verificación de lagunas, deriva interanual, aviso por series cortas <5 años).
- `generic_series_contract.py` — capa reutilizable: rango absoluto, duplicados, brechas, tendencia extrema.

**Isolation Forest** (`src/ieo/observability/anomaly.py`, paso 02 en `pipeline_qc.py`):
- `contamination=0.05` — umbral fijo del 5 % por estrato (valor acordado para el pipeline; más conservador que el `"auto"` de sklearn, ~10 %).
- `random_state=42` — resultado reproducible entre corridas.
- Estratificación por `radial_id` y banda de profundidad (0–20 m / 20–100 m / >100 m).
- Columnas categóricas (`estacion`, `cast`) y columnas con >40% NaN excluidas de las features.
- `top_features` guardado solo para filas anómalas (audit más ligero).

**Tests:** `pip install -r requirements-dev.txt` → `pytest tests/ -v`. No necesitan datos IEO.

---

## Más detalle

- Código activo en `src/`: **[`src/README.md`](src/README.md)**.
- Carpeta `run/`: **[`run/README.md`](run/README.md)**.
- Roadmap técnico: **[`docs/escalabilidad.md`](docs/escalabilidad.md)**.
- TRL, limitaciones (financiación / metodología / alcance TFM): [`docs/posicionamiento_trl.md`](docs/posicionamiento_trl.md).
- Arquitectura de validación: [`docs/arquitectura_validacion_datos.md`](docs/arquitectura_validacion_datos.md).
- Visor Streamlit (mapa, rutas, `data/processed` legacy): [`docs/visor_radiales.md`](docs/visor_radiales.md).
- Integración web IEO: [`docs/integracion_web_ieo.md`](docs/integracion_web_ieo.md).
- Operación y Docker: [`docs/operacion_tfm.md`](docs/operacion_tfm.md).
- Smoke test E2E: `python scripts/e2e_smoke.py --help`.

---

## 🧪 Reproducibilidad y Toy Dataset (Evaluación del Tribunal)

### Por qué no hay datos reales en el repositorio

Los perfiles CTD del mar Cantábrico son propiedad del **Instituto Español de Oceanografía (IEO)** y están sujetos a embargo científico hasta su publicación oficial. No se incluyen en este repositorio público.

### Toy Dataset: `data/demo_cnv/`

La carpeta [`data/demo_cnv/`](data/demo_cnv/) contiene **4 ficheros `.cnv` sintéticos** con formato SeaBird auténtico, diseñados para auditar cada capa de la arquitectura sin necesidad de datos reales:

| Fichero | Comportamiento esperado | Qué ejercita |
|---|---|---|
| `01_happy_path_Gijon.cnv` | Ingesta correcta, clasificado como radial **Gijón** (43.53°N, 5.50°W). Temperatura 15→11 °C (5–200 m), salinidad ~35.5 PSU. | Pipeline completo sin incidencias |
| `02_happy_path_Santander.cnv` | Ingesta correcta, clasificado como radial **Santander** (43.45°N, 3.85°W). Perfil análogo. | Multi-radial en una sola corrida |
| `03_quarantine_broken.cnv` | **Enviado a cuarentena** automáticamente. Sin líneas `# name N = var: …` en la cabecera: el `ingest_gate.py` no detecta columnas CTD y escribe `reasons.json` en `data/quarantine/`. | Control previo (paso 00b) |
| `04_anomaly_stress_test.cnv` | Ingesta correcta, pero a **50 m de profundidad** hay un salto de temperatura a **34.5 °C** (límite físico del contrato: 32 °C). Genera **ERROR** en el contrato radial y la fila es detectada y separada por el **Isolation Forest**. | Contrato de datos (paso 01b) + IF (paso 02) |

### Cómo ejecutarlo (3 pasos)

```bash
# 1. Copiar el toy dataset a la carpeta de ingesta
cp -r data/demo_cnv/* data/cnv/
# En Windows (PowerShell):
# Copy-Item data\demo_cnv\* data\cnv\ -Recurse

# 2. Ejecutar el pipeline
python run/main.py

# 3. Abrir el visor
streamlit run run/app.py
```

Tras la ejecución encontrarás:
- `data/quarantine/` — copia del fichero 03 con su `reasons.json`
- `outputs/runs/<run_id>/checkpoints/02_anomalies.html` — la fila anómala a 50 m del fichero 04
- `outputs/RESUMEN_ULTIMA.html` — resumen visual de toda la corrida
- `outputs/audit_report.md` — generado con `python scripts/audit_report.py`

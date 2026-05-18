# IEO Orchestrator — Radial Cudillero (pipeline + visor)

[![CI](https://github.com/lobatojorge/IEO-Orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/lobatojorge/IEO-Orchestrator/actions/workflows/ci.yml)

## Qué es esto

Un **sistema de auditoría de datos oceanográficos** con tres componentes:

1. **Pipeline reproducible** (`run/main.py`): puerta de cuarentena → ingesta `.cnv` → contrato de calidad → segregación de anomalías (Isolation Forest) → Parquet versionado con `provenance.json`, `run_summary.json` y **`outputs/RESUMEN_ULTIMA.html`** (resumen visual de la última corrida).
2. **Contrato de datos en código** (`src/ieo/validation/`): reglas con severidad ERROR/WARNING versionadas en git y verificadas en CI — no en un documento PDF.
3. **Visor gobernado** (`run/app.py`): muestra el estado de calidad *antes* de cada gráfica; el investigador ve qué pasó antes de interpretar la serie.

La arquitectura es transferible a otros dominios: datos volcánicos, calidad de agua, cualquier serie temporal de sensor. Ver [`docs/arquitectura_validacion_datos.md`](docs/arquitectura_validacion_datos.md) y [`docs/domain_catalog.md`](docs/domain_catalog.md).

**TRL actual: 4** — demo reproducible con datos CTD reales de la radial de Cudillero. Ver [`docs/posicionamiento_trl.md`](docs/posicionamiento_trl.md) para limitaciones honestas y roadmap.

---

## Demo rápida → [`DEMO.md`](DEMO.md)

Pipeline sobre ficheros **SeaBird `.cnv`** y visor **Streamlit** (Marcos + bandas tipo ATAC) para la radial de **Cudillero**. El visor lee los **Parquet** generados por la última corrida del pipeline.

**Modelo en el visor:** tendencia + estacionalidad mensual (Marcos); incertidumbre = residuos **iid gaussianos** (σ constante, **sin AR**). Las líneas solo unen **meses consecutivos** (no se cruzan huecos de campaña).

**Auditoría de clasificación radial en disco:** `python run/audit_cnv_radials.py` → `outputs/temporal/cnv_radial_audit.csv` (generado localmente; no versionado).

---

## Carpetas de datos

| Ubicación | Uso |
|-----------|-----|
| `data/cnv/` | **Entrada en disco:** ficheros `.cnv` de todas las radiales (admite subcarpetas por año). El pipeline **solo procesa Cudillero** (véase abajo). |
| `data/quarantine/` | Ficheros `.cnv` rechazados por la puerta de entrada + `reasons.json`. |
| `outputs/runs/<run_id>/data/*.parquet` | **Entrada del visor**: Parquets `*_ctd_clean.parquet`, `*_ctd_anomalies.parquet`, etc. |
| `outputs/RESUMEN_ULTIMA.html` | **Resumen visual** de la última ejecución de `run/main.py` (se sobrescribe cada vez; en `.gitignore`). |

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

# 2. Coloca los .cnv en data/cnv/ (puedes mezclar radiales; solo se procesa Cudillero)

# 3. Ejecutar el pipeline
python run/main.py           # → solo Cudillero; resumen en outputs/RESUMEN_ULTIMA.html

# 4. Abrir el resumen visual (opcional)
#    outputs/RESUMEN_ULTIMA.html en el navegador

# 5. Lanzar el visor
streamlit run run/app.py     # → elige corrida en la barra lateral
```

**Docker (opcional):** ver [`docs/operacion_tfm.md`](docs/operacion_tfm.md).

---

## Filtro radial (solo Cudillero)

En `data/cnv/` suelen convivir casts de **Gijón, Santander, Vigo, A Coruña y Cudillero**.
Cada `.cnv` trae la radial en metadatos SeaBird, sobre todo:

| Metadato | Ejemplo |
|----------|---------|
| `** Cruise:` | `Radial Santander`, `Radial Gijón`, …; `RCAN_*` / `Radiales Cantábrico` = **campaña**, no radial |
| `** Latitude/Longitude:` | **Principal** para asignar radial si el cruise es ambiguo |
| `** Station:` | Número de estación del cast (E2SA, E2GI, …) |
| Nombre fichero | `gjul101.cnv` → Gijón; prefijo `s` → Santander; `jul301.cnv` sin prefijo → Cudillero (si no hay coords) |

Por defecto el pipeline **no evalúa ni ingiere** ficheros de otras radiales (se omiten sin copiar a cuarentena).
Clasificación en `src/ieo/io/cnv_radial.py` (geo → cruise explícito → nombre).
Así se evita sobrecargar el servidor con miles de perfiles ajenos al producto Cudillero.

- Depuración / procesar todo: `IEO_ALL_RADIALS=1 python run/main.py`
- Límite de prueba: `IEO_MAX_CNV=10 python run/main.py`

La clasificación vive en `src/ieo/io/cnv_radial.py`.

---

## Flujo del pipeline

```
data/cnv/**/*.cnv   (todas las radiales en disco)
                  │
                  ▼ Paso 00a: filtro Cudillero (cnv_radial.py) — omite gijón/santander/…
                  │
                  ▼ Paso 00b: puerta de cuarentena (ingest_gate.py)
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

**Isolation Forest** no sustituye el contrato radial: el contrato aplica **reglas físicas por fila** (rangos, saltos); el IF detecta **combinaciones estadísticamente inusuales** en el conjunto completo. Son capas complementarias.

**Cuarentena de ficheros** vs **segregación de filas**: la puerta de cuarentena (paso 00) actúa sobre el fichero entero antes de tocarlo. El IF actúa sobre las filas ya cargadas. Son niveles distintos de control.

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
│   └── quarantine/                 # .cnv rechazados por la puerta de entrada
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
- `radial_contract.py` — reglas CTD Cantábrico (temperatura, salinidad, gradientes, deriva interanual).
- `generic_series_contract.py` — capa reutilizable: rango absoluto, duplicados, brechas, tendencia extrema.

**Tests:** `pip install -r requirements-dev.txt` → `pytest tests/ -v`. No necesitan datos IEO.

---

## Más detalle

- Código activo en `src/`: **[`src/README.md`](src/README.md)**.
- Carpeta `run/`: **[`run/README.md`](run/README.md)**.
- Roadmap técnico: **[`docs/escalabilidad.md`](docs/escalabilidad.md)**.
- TRL, limitaciones: [`docs/posicionamiento_trl.md`](docs/posicionamiento_trl.md).
- Arquitectura de validación: [`docs/arquitectura_validacion_datos.md`](docs/arquitectura_validacion_datos.md).
- Integración web IEO: [`docs/integracion_web_ieo.md`](docs/integracion_web_ieo.md).
- Operación y Docker: [`docs/operacion_tfm.md`](docs/operacion_tfm.md).
- Smoke test E2E: `python scripts/e2e_smoke.py --help`.

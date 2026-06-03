# Demo — IEO Orchestrator (radiales Cantábrico)

Reproducir la demo completa en 3 comandos.  
Tiempo estimado: 2–5 minutos (depende del número de ficheros `.cnv`).

---

## Requisitos previos

| Requisito | Verificación |
|-----------|-------------|
| Python 3.11+ | `python --version` |
| Ficheros SeaBird | `data/cnv/**/*.cnv` (no incluidos en git; copiar desde el archivo del buque) |
| Dependencias | `pip install -r run/requirements.txt` |

> Si no tienes `.cnv` a mano, puedes abrir el visor si existe una corrida previa bajo `outputs/runs/`.

---

## Los 3 comandos

```bash
# 0. Coloca los .cnv en data/cnv/ (mezcla de radiales OK; el pipeline ingiere todas por defecto)

# 1. Pipeline (consola estructurada: datos → pasos → barras de progreso → resultados → hint Streamlit)
python run/main.py

# 2. Smoke test: verifica que los artefactos son correctos sin abrir el visor
python scripts/e2e_smoke.py --skip-pipeline

# 3. Visor: demo Gijón (Parquet de corrida si existe; si no, `.cnv`); estaciones por botones
streamlit run run/app.py
```

El visor arranca en `http://localhost:8501`.

Al final del paso 02, la consola muestra **cuántas filas** marcó Isolation Forest (`contamination=0.05`, 5 % por estrato) y **dónde revisarlas** (Parquet `*_ctd_anomalies`, `checkpoints/02_anomalies.html`, `outputs/RESUMEN_ULTIMA.html`) — sin listar cada fichero en pantalla.

---

## Qué produce el pipeline

Bajo `outputs/runs/<run_id>/` (generado automáticamente con timestamp):

```
outputs/runs/<run_id>/
├── provenance.json                              # qué .cnv entró, cuándo, con qué parámetros
├── run_summary.json                             # resumen estructurado de la corrida
├── data/
│   ├── perfiles_all.ctd_canonical.parquet      # tabla normalizada (todas las filas)
│   ├── perfiles_all.ctd_clean.parquet          # filas válidas según Isolation Forest
│   ├── perfiles_all.ctd_anomalies.parquet      # filas segregadas (no eliminadas)
│   └── perfiles_all.ctd_anomaly_audit.parquet  # registro del modelo de anomalías
└── checkpoints/
    ├── 00_gate_rejected.html    (si el fichero fue rechazado)
    ├── 01_ingestion.html
    ├── 01b_radial_contract.html  # contrato (T/S/prof + años en `fecha`)
    ├── 02_anomalies.html
    └── 03_quality.html           # resumen de salud para no técnicos
```

Además, cada ejecución actualiza **`outputs/RESUMEN_ULTIMA.html`** (resumen visual de la última corrida; en `.gitignore`).

---

## Qué ver en el visor

1. **Embudo y mapa Cantábrico** — narrativa de pasos (early warning) + contexto geográfico (**Gijón** resaltado; la demo está fijada a esta radial).
2. **Pestañas Temperatura / Salinidad** — botones de estación (E1GI–E4GI en Gijón); profundidad activa 5 m.
3. **Serie a 5 m** — marcadores por campaña; pronóstico solo del **último mes** (no usado en el ajuste).
4. **Transecto (abajo)** — metodología y mapa del transecto; la estación elegida es la de los **botones de arriba** (no hay que depender del clic en el mapa).

---

## Variables de entorno útiles

| Variable | Efecto |
|----------|--------|
| `IEO_PIPELINE_RADIAL=cudillero` (u otro id) | Acota la corrida a ficheros clasificados como esa radial (misma cadena de validación; menos CPU). Ids: `cudillero`, `gijon`, `santander`, `coruna`, `vigo`. |
| `IEO_ONLY_CUDILLERO=1` | Equivale a `IEO_PIPELINE_RADIAL=cudillero` (compatibilidad). |
| `IEO_ALL_RADIALS=1` | Redundante con el valor por defecto (se muestra aviso en consola). |
| `IEO_MAX_CNV=N` | Limita a los primeros N ficheros aceptados. |
| `IEO_FULL_REBUILD=1` | Ignora caché incremental; reprocesa todo. |
| `IEO_QC_WORKERS=N` | Procesos paralelos en calidad/anomalías (por defecto ≈ CPU−1, máx. 8). |
| `IEO_REUSE_QC=0` | Fuerza recalcular Isolation Forest en el run actual. |
| `IEO_SAMPLING_YEAR_MIN` / `IEO_SAMPLING_YEAR_MAX` | Ajustan el rango de años permitido en la columna canónica `fecha` (contrato 01b y QC del visor). Ver [`docs/contrato_datos_radiales.md`](docs/contrato_datos_radiales.md). |

---

## Más documentación

- [`README.md`](README.md) — visión general y arquitectura
- [`run/README.md`](run/README.md) — scripts de ejecución
- [`docs/operacion_tfm.md`](docs/operacion_tfm.md) — Docker, CI, troubleshooting
- [`docs/posicionamiento_trl.md`](docs/posicionamiento_trl.md) — TRL 4, limitaciones por origen (financiación / metodología / TFM)

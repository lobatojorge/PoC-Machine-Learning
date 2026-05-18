# Demo — IEO Orchestrator (Radial Cudillero)

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
# 0. Coloca los .cnv en data/cnv/ (pueden mezclarse radiales; solo se procesa Cudillero)

# 1. Pipeline: puerta de cuarentena → ingesta .cnv → contrato de calidad → Isolation Forest → Parquet
python run/main.py

# 2. Smoke test: verifica que los artefactos son correctos sin abrir el visor
python scripts/e2e_smoke.py --skip-pipeline

# 3. Visor: exploración interactiva con tarjetas de calidad
streamlit run run/app.py
```

El visor arranca en `http://localhost:8501`.

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
    ├── 01b_radial_contract.html  # resultado del contrato de datos
    ├── 02_anomalies.html
    └── 03_quality.html           # resumen de salud para no técnicos
```

Además, cada ejecución actualiza **`outputs/RESUMEN_ULTIMA.html`** (resumen visual de la última corrida; en `.gitignore`).

---

## Qué ver en el visor

1. **Tarjetas de proveniencia** — ingesta `.cnv`, QC, anomalías, análisis Marcos+ATAC.
2. **Pestañas por estación** — serie mensual a 5 m (T y S).
3. **Gráfico Marcos + bandas** — tendencia, estacionalidad, residuos iid (sin AR).
4. **Mapa del transecto** — clic en estación para cambiar pestaña.

---

## Variables de entorno útiles

| Variable | Efecto |
|----------|--------|
| `IEO_ALL_RADIALS=1` | Procesa todas las radiales en `data/cnv/` (depuración). |
| `IEO_MAX_CNV=N` | Limita a los primeros N ficheros aceptados. |

---

## Más documentación

- [`README.md`](README.md) — visión general y arquitectura
- [`run/README.md`](run/README.md) — scripts de ejecución
- [`docs/operacion_tfm.md`](docs/operacion_tfm.md) — Docker, CI, troubleshooting

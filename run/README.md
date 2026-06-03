# Carpeta `run/` — Ejecución

Punto de entrada del **pipeline multi-radial** y del **visor Streamlit** (demo priorizada en Gijón).

| Archivo | Rol |
|---------|-----|
| `main.py` | Pipeline multi-radial: misma cadena para todas las radiales en `data/cnv/` por defecto. Alcance opcional `IEO_PIPELINE_RADIAL=<id>`. Compatibilidad: `IEO_ONLY_CUDILLERO=1`. `RESUMEN_ULTIMA.html` siempre. Ver [`docs/visor_radiales.md`](../docs/visor_radiales.md). |
| `app.py` | Visor hub Cantábrico: abre en **Gijón**; Parquet filtrado por radial o `.cnv`; tarjetas de pipeline sobre mapa transecto; holdout 1 mes; ver [`docs/visor_radiales.md`](../docs/visor_radiales.md). |
| `preflight_cnv.py` | Inventario y «diálogo» automático para lotes bajo carpetas sin convención `AAAA/` (p. ej. `St.1 CNVs`): preguntas, dubios y puerta de ingesta. |
| `audit_cnv_radials.py` | Auditoría clasificación `.cnv` → `outputs/temporal/cnv_radial_audit.csv` |
| `pipeline_runs.py` | Resolución de corridas y carga de Parquet para el visor |
| `ieo_cli.py` | Alias CLI: `python run/ieo_cli.py run` |
| `requirements.txt` | Dependencias del pipeline y del visor |
| `lanzador.bat` | Arranque rápido Windows (venv + Streamlit) |

## Carpetas de datos

| Carpeta | Rol |
|---------|-----|
| `data/cnv/` | **Entrada del pipeline:** `.cnv` en cualquier subcarpeta (convención `AAAA/` u otras, p. ej. `St.1 CNVs`). Preflight: `python run/preflight_cnv.py`. |
| `data/quarantine/` | Ficheros rechazados + `reasons.json` explicando el motivo. |

> **Trazabilidad:** cada corrida genera `outputs/runs/<run_id>/provenance.json` con el SHA256
> de cada fichero de entrada, la versión de Python, la plataforma y los parámetros de la corrida.

## Resumen visual

Tras cada `python run/main.py` se genera **`outputs/RESUMEN_ULTIMA.html`**: página HTML única con estado, métricas, enlaces a JSON y checkpoints de la última corrida. Está en `.gitignore`. La consola imprime su ruta al final si existe.

## Salida en consola (estructura)

Cada `python run/main.py` imprime en stderr, en este orden:

1. **Datos de entrada** — inventario `data/cnv/` por ciudad, alcance (`IEO_PIPELINE_RADIAL`), modo incremental o completo.
2. **Pasos del pipeline** — control previo → ingesta → contrato → anomalías → consolidación.
3. **Progreso** — barras por paso (sin listar cada `.cnv` ni volcar código).
4. **Resultados consultables** — métricas, **total de anomalías solo al terminar el 100 %** del paso 02, rutas a Parquet/checkpoints/HTML.
5. **Streamlit** — comando `streamlit run run/app.py`.

## Demo oficial (reunión / TRL 4)

```bash
# 1. Instalar dependencias (una sola vez)
pip install -r run/requirements.txt

# 2. Colocar los .cnv en data/cnv/ (pueden convivir Gijón, Santander, Cudillero, …;
#    también subcarpetas sin año, p. ej. St.1 CNVs)

# 2b. (Recomendado si hay carpetas nuevas) Preflight: preguntas + dubios + JSON
python run/preflight_cnv.py

# 3. Ejecutar el pipeline (incremental por defecto)
python run/main.py

# 4. Visor (usa perfiles_all.ctd_clean.parquet de la última ejecución)
streamlit run run/app.py
```

## Modos de ejecución: completo vs incremental

| Modo | Cuándo | Comando |
|------|--------|---------|
| **Incremental** (por defecto) | Día a día: solo `.cnv` nuevos o modificados | `python run/main.py` |
| **Reconstrucción completa** | Cambió el lector CNV, el contrato o quieres invalidar caché | `$env:IEO_FULL_REBUILD = "1"; python run/main.py` |

El modo incremental mantiene:

- `outputs/pipeline_manifest.json` — índice ruta relativa → SHA256 + rutas en caché.
- `outputs/artifact_cache/` — Parquet canónicos y QC reutilizables entre ejecuciones.

En cada run nuevo se copian al directorio `outputs/runs/<run_id>/data/` solo los artefactos necesarios; no se re-ingiere ni se re-ejecuta Isolation Forest si el fichero fuente no cambió.

## Rendimiento del paso «calidad y anomalías»

Con miles de `.cnv`, el paso 02 (contrato + Isolation Forest por perfil) es el más pesado. Por defecto:

- **Incremental global:** caché entre runs (manifiesto + `artifact_cache`).
- **Paralelo:** hasta 8 procesos (`IEO_QC_WORKERS`).
- **Árboles adaptativos:** menos `n_estimators` en perfiles pequeños (tope 200).
- **Isolation Forest:** `contamination=0.05` (5 % de filas atípicas esperadas por estrato radial × profundidad); `random_state=42`.
- **Reutilización en el mismo run:** `IEO_REUSE_QC=1` (por defecto).

Variables opcionales:

| Variable | Efecto |
|----------|--------|
| `IEO_FULL_REBUILD=1` | Ignora caché; re-ingiere y recalcula todo. |
| `IEO_QC_WORKERS` | Procesos en paralelo para el paso 02 (por defecto ≈ CPU−1, máx. 8). |
| `IEO_REUSE_QC=0` | Fuerza recalcular anomalías aunque los Parquet limpios existan en el run. |
| `IEO_IF_N_ESTIMATORS` | Tope de árboles por perfil (por defecto 200). |
| `IEO_MAX_CNV` | Limita ficheros ingeridos (pruebas rápidas). |

**Primera** corrida completa (~3500 ficheros): del orden de **10–30 min** según CPU. **Siguientes** corridas sin cambios en `data/cnv/`: suele limitarse a consolidación y lectura de manifiesto (minutos o menos). Errores QC en pocos perfiles no bloquean `perfiles_all` (código 0 con aviso `02_anomalies_partial`).

## Códigos de salida de `main.py`

| Código | Significado |
|--------|-------------|
| 0 | Pipeline completado sin errores. |
| 1 | Error en ingesta o detección de anomalías (ver `checkpoints/`). |
| 2 | No se encontraron ficheros `.cnv` en `data/cnv/` (ni subcarpetas). |
| 3 | Todos los ficheros rechazados en el control previo (cuarentena; ver `data/quarantine/`). |

## Código activo en `src/`

Ver [`src/README.md`](../src/README.md) para el mapa completo de módulos.

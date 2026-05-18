# Carpeta `run/` — Ejecución

Punto de entrada del **pipeline Cudillero** y del **visor Streamlit**.

| Archivo | Rol |
|---------|-----|
| `main.py` | Pipeline completo → `outputs/runs/<run_id>/` + **`outputs/RESUMEN_ULTIMA.html`** (resumen visual de la última corrida) |
| `app.py` | Visor Radiales Cudillero (lee Parquet de la última corrida) |
| `audit_cnv_radials.py` | Auditoría clasificación `.cnv` → `outputs/temporal/cnv_radial_audit.csv` |
| `pipeline_runs.py` | Resolución de corridas y carga de Parquet para el visor |
| `ieo_cli.py` | Alias CLI: `python run/ieo_cli.py run` |
| `requirements.txt` | Dependencias del pipeline y del visor |
| `lanzador.bat` | Arranque rápido Windows (venv + Streamlit) |

## Carpetas de datos

| Carpeta | Rol |
|---------|-----|
| `data/cnv/` | **Única entrada del pipeline:** ficheros `.cnv` (todas las radiales en disco; solo se procesa Cudillero salvo `IEO_ALL_RADIALS=1`). |
| `data/quarantine/` | Ficheros rechazados + `reasons.json` explicando el motivo. |

> **Trazabilidad:** cada corrida genera `outputs/runs/<run_id>/provenance.json` con el SHA256
> de cada fichero de entrada, la versión de Python, la plataforma y los parámetros de la corrida.

## Resumen visual

Tras cada `python run/main.py` se genera **`outputs/RESUMEN_ULTIMA.html`**: página HTML única con estado, métricas, enlaces a JSON y checkpoints de la última corrida. Está en `.gitignore`. La consola imprime su ruta al final si existe.

## Demo oficial (reunión / TRL 4)

```bash
# 1. Instalar dependencias (una sola vez)
pip install -r run/requirements.txt

# 2. Colocar los .cnv en data/cnv/ (pueden convivir Gijón, Santander, Cudillero, …)

# 3. Ejecutar el pipeline (solo Cudillero; IEO_ALL_RADIALS=1 para todas)
python run/main.py

# 4. (Opcional) Abrir outputs/RESUMEN_ULTIMA.html en el navegador

# 5. Lanzar el visor
streamlit run run/app.py
```

## Códigos de salida de `main.py`

| Código | Significado |
|--------|-------------|
| 0 | Pipeline completado sin errores. |
| 1 | Error en ingesta o detección de anomalías (ver `checkpoints/`). |
| 2 | No se encontraron ficheros `.cnv` en `data/cnv/` (ni subcarpetas). |
| 3 | Todos los ficheros rechazados por la puerta de cuarentena (ver `data/quarantine/`). |

## Código activo en `src/`

Ver [`src/README.md`](../src/README.md) para el mapa completo de módulos.

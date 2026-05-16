# Carpeta `run/` — Ejecución

Punto de entrada del **pipeline Cudillero** y del **visor Streamlit**.

| Archivo | Rol |
|---------|-----|
| `main.py` | Pipeline completo → `outputs/runs/<run_id>/` |
| `app.py` | Visor Radiales Cudillero (lee Parquet de la última corrida) |
| `pipeline_runs.py` | Resolución de corridas y carga para el visor |
| `build_processed_from_raw.py` | CSV largo en `data/raw/` → `data/processed/perfiles_all.csv` |
| `ieo_cli.py` | Alias CLI: `python run/ieo_cli.py run` |
| `requirements.txt` | Dependencias del visor |
| `lanzador.bat` | Arranque rápido Windows (venv + Streamlit) |

## Demo oficial (reunión / TRL 4)

```bash
# Desde la raíz del repo
pip install -r run/requirements.txt
python run/main.py
streamlit run run/app.py
```

Entrada del pipeline: `data/processed/perfiles_all.csv` (ver README raíz).

Smoke sin re-ejecutar pipeline:

```bash
python scripts/e2e_smoke.py --skip-pipeline
```

## Nota sobre código legacy

Los scripts `src/00_*.py` (Gijón / Excel) no son la ruta de demo actual. Usar `run/main.py` + paquete `src/ieo/`.

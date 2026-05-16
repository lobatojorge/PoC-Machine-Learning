# Operación del sistema (TFM) — TRL acotado y despliegue local

Este documento resume cómo **operar** el demostrador (pipeline + visor), el marco **TRL 7 acotado** usado en el TFM y lo que queda **fuera de alcance**.

## TRL 7 acotado (narrativa para memoria)

Se declara **TRL 7 en sentido acotado**: prototipo **funcional y reproducible** en un entorno controlado (máquina local o contenedor), con **trazabilidad de corrida** (`outputs/runs/<run_id>/`, `provenance.json`), **validación física** (contrato radial) y **detección de anomalías** (Isolation Forest), más **interfaz** (Streamlit) para inspección.

No se afirma equivalencia con producto industrial: sin SLA, sin multi-tenant, sin observabilidad 24/7 ni gobernanza de datos de catálogo corporativo.

## Orden de ejecución

1. Colocar o generar `data/processed/perfiles_all.csv` (ver `README.md`).
2. `python run/main.py` — genera Parquet y reportes bajo `outputs/runs/<run_id>/` (o desde el visor: barra lateral **Ejecutar pipeline ahora**).
3. `streamlit run run/app.py` (desde `run/`) — en la barra lateral, elegir **Última corrida** o un `run_id` concreto; revisar **Provenance** si existe `provenance.json`.

El visor **no** lee el CSV directamente: lee `data/perfiles_all.ctd_clean.parquet` (y anomalías) de la corrida seleccionada.

## Docker (opcional)

Construcción en la raíz del repositorio:

```bash
docker build -t ieo-radiales-visor .
docker run --rm -p 8501:8501 -v "%CD%/outputs:/app/outputs" -v "%CD%/data:/app/data" ieo-radiales-visor
```

En PowerShell, sustituir `%CD%` por la ruta actual (por ejemplo `${PWD}`).

Con Compose:

```bash
docker compose up --build
```

Los volúmenes montan `outputs/` (Parquet de corridas) y `data/` (CSV processed). Sin ellos, el contenedor no verá corridas ni entrada CSV salvo que se copien dentro de la imagen (no recomendado para datos reales).

## Tests automáticos

```bash
pip install -r run/requirements.txt -r requirements-dev.txt
pytest
```

Las pruebas cubren utilidades puras en `run/pipeline_runs.py` (listado de corridas, carga Parquet, token de frescura, provenance).

## Fuera de alcance / trabajo futuro

| Tema | Motivo de exclusión en este TFM |
|------|-----------------------------------|
| Great Expectations (o suites declarativas equivalentes) | Alcance y tiempo; el contrato radial + IF cubren el demostrador. |
| Redes neuronales de grafos (GNN) u otras DL | No hay requisito de modelo estructural en grafos para la radial tabular actual. |
| Ingestión por API, audio o logs operativos | Dominio distinto; pipeline centrado en CSV/CTD canónico. |
| Registry de modelos (MLflow, etc.) | Isolation Forest es baseline reproducible con semilla fija. |
| Despliegue cloud gestionado (K8s, PaaS) | TRL 7 acotado = local/Docker; cloud como extensión futura. |
| Lakehouse / catálogo de datos (OpenMetadata, etc.) | Complejidad organizativa fuera del alcance académico del TFM. |

## Decisiones de implementación (robustez vs coste)

- **QC temperatura en visor:** misma ruta que el pipeline (`validate_canonical_ctd_polars` sobre el limpio).
- **Marcos+ATAC y `audit_log` IF:** no integrados; la pestaña IF y los Parquet `ctd_anomaly_audit` cubren la revisión sin rediseñar el informe ATAC.
- **Salinidad:** el wrapper canónico Polars solo cubre T; la S sigue con `validate_profile_dataframe` (reglas análogas de perfil).
- **Botón «Ejecutar pipeline»:** `subprocess.run` síncrono en la misma máquina (sin colas ni workers); adecuado para TFM sin coste de nube.

## Límites conocidos

- El visor depende de que exista al menos una corrida con `perfiles_all.ctd_clean.parquet`.
- La caché de Streamlit se invalida con el token `mtime_ns` + `size` del Parquet limpio; si se borra una corrida seleccionada, recargar la página o elegir otra corrida.
- `docker compose` no ejecuta el pipeline automáticamente: conviene documentar en la memoria el flujo en dos pasos (pipeline → visor).

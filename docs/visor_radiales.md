# Visor Streamlit — hub de radiales Cantábrico

Este documento describe el comportamiento actual de [`run/app.py`](../run/app.py) y cómo se relaciona con el pipeline y los datos en disco.

## Salida del pipeline y visor

- **`run_summary.json`** / consola / **`RESUMEN_ULTIMA.html`**: inventario + bloque de corrida (por defecto **todas** las radiales con la misma cadena de validación). Con `IEO_PIPELINE_RADIAL=<id>` el bloque refleja el alcance acotado.
- **Cuarentena / logs stderr**: los ficheros rechazados se muestran como `AAAA/nombre.cnv` cuando el `.cnv` está bajo una carpeta-año (p. ej. `2019/foo.cnv`).
- **`outputs/RESUMEN_ULTIMA.html`**: también se genera si la corrida falla con una excepción no gestionada (campo `fatal_error` + trazado recortado en el HTML).

## Qué hace el visor (versión demo / presentación)

- **Radial fija:** `radial_id = gijon`. La página está montada como **Early Warning**: hero + franja de embudo («del dato de campaña a lo que ves») en [`run/viewer_presentation.py`](../run/viewer_presentation.py), sin destacar herramientas internas salvo uso técnico.
- **Sidebar de Streamlit:** oculto por CSS (`inject_presentation_css`) para no distraer en reunión divulgativa.
- **Mapa Cantábrico (Plotly):** todas las ciudades con datos visibles como referencia; **Gijón** resaltada. El mapa es **solo contexto geográfico** (no debe usarse como paso de sección del dato cargado ni para rerun pesado por selección Plotly).
- **Orden de carga:** indexación geo mínima → **carga de datos Gijón** (Parquet o `.cnv`) **antes** de pintar ese mapa, para que el spinner de ingestión no parezca “al hacer clic en un punto”.
- **Datos por radial (Gijón):**
  - Si existe corrida válida con Parquet limpio bajo `outputs/runs/`, se cargan datos de la corrida seleccionados y **se filtran a `radial_id=gijon`** (`filter_dataframe_to_radial`: misma infraestructura que el resto de radiales).
  - Si esa corrida **no tiene filas de Gijón**, se puede caer automáticamente a lectura de `.cnv` clasificados en `data/cnv/` solo para ese radial (con mensaje si el Parquet existe pero viene vacío).
  - Mensajes muy técnicos de “otras radiales en el parquet” están **silenciados** para la demo cuando no ayudan a la narrativa.
- **Columna `estacion`:** la carga desde `.cnv` rellena `estacion` desde la cabecera `** Station:` cuando falta en el bloque de datos; en UI predominan índices **canónicos 1–N** (`E1GI`–`E4GI`): ver [`glosario_estaciones_radiales.md`](glosario_estaciones_radiales.md).

## Presentación radial y series

Tras cargar datos, el bloque “2 · … · Estación y series” incluye badges de cobertura, última campaña y **fuente** (`pipeline` si Parquet corrida, `cnv` si lectura desde disco sin pasar por parquet del visor en ese momento).

- **Selección de estación:** pestañas Temperatura / Salinidad con **filas de botones** por estación (no depender solo del clic en marcadores Plotly para evitar reruns innecesarios). Una estación con datos disponible suele estar **precargada** en la primera apertura.
- **Transecto (final de página):** texto metodología; mapa Plotly **solo ubicación**. La estación activa coincide con los botones de pestañas (los mapas ya no tienen rol de selección primaria para la UX de demo).

### Series temporales (T / S @ 5 m)

- Agregación mensual en `monthly_at_depth.py`: si hay **varios CTD en el mismo mes**, se conserva el lance con **mayor profundidad máxima** del perfil (roseta repetida).
- Modelo Marcos + bandas iid (`atac_monthly_report.py`): **holdout de 1 mes** (último con observación, excluido del ajuste).
- Gráfico: **solo marcadores** en observación, ajuste histórico y pronóstico; sin polilíneas entre huecos entre campañas.
- Contrato radial: errores pueden **bloquear** la gráfica hasta desbloqueo explícito de diagnóstico; avisos (WARNING) pueden mostrarse bajo la serie.

## Clasificación geográfica (mapa y agregación)

La posición de cada ciudad en el mapa resumen es la **mediana** de coordenadas de casts clasificados como esa radial (ver `src/ieo/reports/radial_cnv_geo.py`). La asignación por lat/lon está en `src/ieo/io/cnv_radial.py` → `classify_radial_by_position`: **A Coruña** se acota a **Galicia occidental** (longitud ≤ −7° y latitud en banda costera/plataforma), evitando etiquetar como Coruña el mar al norte de Gijón.

## Caché del índice geo (rendimiento)

- En cada rerun de Streamlit se calcula **una sola vez** una huella del árbol `*.cnv` bajo `data/cnv/`: `cnv_data_tree_fingerprint` en `src/ieo/cnv_layout.py` (conteo + `mtime_ns` máximo).
- El resultado serializable del índice geo (ciudades, estaciones Plotly, contadores) se guarda en **`outputs/temporal/radial_geo_index.cache.json`** junto con la misma huella en el campo `token`. Si al arrancar el token coincide, se **reutiliza** el JSON y se evita reindexar miles de cabeceras.
- Ese directorio está en `.gitignore`; al cambiar o añadir `.cnv`, la huella cambia y el índice se reconstruye.

## `data/processed` vs pipeline CNV

| Ruta | Rol |
|------|-----|
| `outputs/runs/<run_id>/` | Auditoría e ingesta del **pipeline CNV** (`run/main.py`): checkpoints HTML, métricas, Parquet. |
| `data/processed/` | **Legacy** (inspector CSV / Sireno en scripts antiguos). **No** es requisito del pipeline CNV ni del visor actual. |

Los `.cnv` **sí** se auditan en el pipeline (control previo / cuarentena, contrato, Isolation Forest, etc.); eso **no** depende de que exista `data/processed/`.

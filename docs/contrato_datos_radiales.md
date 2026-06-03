# Contrato de datos · Radiales Cantábrico (visor + pipeline)

Este documento describe las reglas que implementa `src/ieo/validation/radial_contract.py`.

## Dónde se aplica

| Entrada | Momento |
|---------|---------|
| Parquet **limpio** (`*.ctd_clean.parquet`) en **Streamlit** (`run/app.py`) | Tras cargar la corrida y **antes** de Marcos+ATAC (misma lógica que 01b para T en perfil). Si hay violaciones **ERROR**, el gráfico **no se muestra** salvo checkbox explícito de diagnóstico. |
| Parquet **canónico** (`*.ctd_canonical.parquet`) | Paso **01b** del pipeline (`run/main.py`): informe en `outputs/runs/<run>/checkpoints/` y mensaje en stderr si hay errores. |

## Umbrales por defecto (`RadialContractThresholds`)

Ajustables en código según región / producto.

### Perfil (filas)

- **Temperatura**: valores en \([-2, 32]\) °C (Cantábrico superficial / orden de magnitud).
- **Salinidad**: \([0, 42]\) PSU.
- **Saltos verticales — temperatura**: entre niveles adyacentes (conservando el orden cronológico de adquisición sin reordenar), con detección de "resets" de profundidad para separar lances. Dos bandas de Δz (m): hasta \(~5\) m y hasta \(~15\) m, con aviso/error configurables.
- **Saltos verticales — salinidad** *(nuevo)*: mismas bandas Δz que temperatura con umbrales PSU/m (aviso ≥ 3 PSU/m, error ≥ 8 PSU/m en banda corta).
- **Variables `other`** (O₂ disuelto, fluorescencia, turbidez): actualmente sin regla de gradiente vertical. Ampliar `infer_variable_kind` en `radial_contract.py` para añadirlas.

### Fecha de muestreo (`fecha`)

- La columna canónica **`fecha`** debe ser parseable; si **todas** las filas son NaT → **ERROR** `sampling_date_unparseable`.
- Si solo parte son NaT → **WARNING** `sampling_date_partially_missing`.
- El **año calendario** debe estar en \([`sampling_year_min`, `sampling_year_max`]\) (por defecto **1970–2035**). Fuera de ese rango → **ERROR** `sampling_date_out_of_calendar_range` (evita metadatos aberrantes que estiran el eje temporal del visor).
- Overrides opcionales vía entorno: **`IEO_SAMPLING_YEAR_MIN`** y **`IEO_SAMPLING_YEAR_MAX`** (enteros; si el par resultante es incoherente se ignoran y se usan los valores por defecto del dataclass).

### Serie mensual agregada

- **Saltos** entre dos puntos **consecutivos en el tiempo** (tras ordenar por fecha): aviso 6 °C, **error 12 °C** (temperatura). *Solo se aplica entre pares con laguna ≤ 3 meses*; si hay un hueco mayor (p. ej. enero a octubre) ese par se omite para evitar falsos positivos.
- **Deriva fina** (solo temperatura): pendiente de la **mediana anual** vs año; aviso si |pendiente| ≥ 0,25 °C/año; error si ≥ 0,6 °C/año. Solo para series con **≥ 5 años** de datos.
- **Serie corta** *(nuevo)*: si la serie tiene < 5 años, se emite WARNING `series_too_short_for_trend` en lugar de silencio (posible instrumento recién calibrado o error de metadatos).
- **Ventanas**: diferencia de medianas anuales entre los últimos 3 años y los 3 anteriores; aviso si |Δ| ≥ 0,8 °C.

## Limitaciones declaradas

- Los saltos "mes a mes" se aplican solo entre pares con brecha temporal ≤ 3 meses calendario (`month_gap_max_for_consecutive_rule`). Brechas mayores se omiten.
- Variables `other` (O₂, fluorescencia, turbidez) no disparan reglas de gradiente vertical por defecto.
- La regla de tendencia interanual requiere ≥ 5 años de datos; con menos emite `series_too_short_for_trend` en lugar de silencio.
- Los umbrales de salinidad vertical (PSU/m) son conservadores y pueden ajustarse para campañas con surgencias fuertes.

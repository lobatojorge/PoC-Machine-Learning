# Contrato de datos · Radiales Cudillero (visor + pipeline)

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
- **Saltos verticales** entre niveles adyacentes ordenados por profundidad (tras partir por segmentos monótonos de `z`): se ignoran pares con **Δz** por debajo de `temp_adjacent_min_dz_m` (ruido casi coplanar). Luego dos bandas: **Δz** hasta ~5 m y **Δz** hasta 15 m, cada una con aviso/error propios (`temp_adjacent_delta_warn_band_*`, `temp_adjacent_delta_error_band_*` en `RadialContractThresholds`).

### Serie mensual agregada

- **Saltos** entre dos puntos **consecutivos en el tiempo** (tras ordenar por fecha): aviso 6 °C, **error 12 °C** (temperatura).
- **Deriva fina** (solo temperatura): pendiente de la **mediana anual** vs año; aviso si |pendiente| ≥ 0,25 °C/año; error si ≥ 0,6 °C/año.
- **Ventanas**: diferencia de medianas anuales entre los últimos 3 años y los 3 anteriores; aviso si |Δ| ≥ 0,8 °C.

## Limitaciones declaradas

- Los saltos “mes a mes” usan **puntos consecutivos en la serie observada**; si faltan meses, el salto puede abarcar más de un mes calendario.
- Variables no térmicas / no salinas no disparan estas reglas (se puede ampliar `infer_variable_kind`).

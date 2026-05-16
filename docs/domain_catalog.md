# Catálogo de dominios — cómo añadir una nueva campaña al sistema

Este documento explica, paso a paso, cómo adaptar el pipeline y el contrato
de datos a un **nuevo dominio científico**: otra radial oceanográfica, datos de
sensores volcánicos, series de calidad de agua, etc.

La arquitectura está diseñada para que el dominio concreto (Cudillero) sea una
instancia de un patrón genérico, no la única instancia posible.

---

## Qué necesitas para un nuevo dominio

| Elemento | Mínimo | Óptimo |
|----------|--------|--------|
| Datos tabulares (CSV / Parquet) | Sí | + formato `.cnv` o binario con reader específico |
| Variable principal numérica (temperatura, presión, SO₂…) | Sí | + variables secundarias |
| Identificador de estación o sensor | Sí | + metadatos de campaña |
| Dimensión temporal (fecha/hora) | Sí | Con zona horaria o UTC explícito |
| Umbrales físicos del dominio | Sí | Documentados en publicación |
| Experto de dominio para validar umbrales | Recomendado | Necesario para TRL 5 |

---

## Paso 1: Registrar el dominio en el catálogo

Añadir el nuevo dominio a `src/ieo/radiales_catalog.py`:

```python
# radiales_catalog.py
RADIAL_ID_VOLCANICO = "volcanico_tenerife"   # id interno, minúsculas

RADIAL_STATION_CODES: dict[str, tuple[str, ...]] = {
    # ... entradas existentes ...
    RADIAL_ID_VOLCANICO: ("F01TF", "F02TF", "F03TF"),  # códigos de fumarola
}
```

Los códigos son cadenas que aparecen en el acrónimo o identificador de cast del CSV.
La función `identify_radial(text)` los detecta por substring (más largo primero).

---

## Paso 2: Definir umbrales específicos del dominio

Usar `GenericContractThresholds` (independiente del dominio) o extender
`RadialContractThresholds` para el dominio concreto.

### Opción A — contrato genérico (recomendada para empezar)

```python
from ieo.validation.generic_series_contract import (
    GenericContractThresholds, run_generic_contract
)

UMBRALES_VOLCANICO = GenericContractThresholds(
    abs_min=20.0,       # temperatura fumarola: mínimo físico esperado (°C)
    abs_max=800.0,      # temperatura fumarola: máximo físico esperado (°C)
    max_gap_days=95,    # más de 3 meses sin dato = aviso
    warn_trend_per_year=5.0,   # +5 °C/año = aviso de deriva o señal real
    max_trend_per_year=20.0,   # +20 °C/año = posible fallo de calibración
    min_years_for_trend=5,
)

violaciones = run_generic_contract(
    df,
    col_time="fecha_utc",
    col_value="temp_fumarola_c",
    col_id="punto_medida",
    variable_name="temperatura fumarola",
    units="°C",
    thresholds=UMBRALES_VOLCANICO,
)
```

### Opción B — contrato de dominio propio (para reglas físicas específicas)

Crear `src/ieo/validation/volcanic_contract.py` siguiendo el mismo patrón
que `radial_contract.py`:

```python
from ieo.validation.radial_contract import Violation, ViolationSeverity

def validate_fumarola_series(df, *, thresholds) -> list[Violation]:
    violations: list[Violation] = []
    # Añadir reglas específicas (p. ej. razón SO₂/CO₂, anomalías sísmicas correladas)
    ...
    return violations
```

---

## Paso 3: Filtrar el DataFrame al dominio correcto

```python
from ieo.radiales_catalog import filter_dataframe_to_radial, RADIAL_ID_VOLCANICO

df_dominio, n_descartados = filter_dataframe_to_radial(df_completo, RADIAL_ID_VOLCANICO)
if n_descartados > 0:
    print(f"[catalog] {n_descartados} filas de otras campañas eliminadas")
```

Si el CSV solo contiene datos de una campaña, este paso puede omitirse.

---

## Paso 4: Ejecutar el pipeline con el nuevo dominio

El pipeline actual (`run/main.py`) está parametrizado para Cudillero vía `run/ieo_cli.py`.
Para un nuevo dominio:

1. Copiar `run/main.py` → `run/main_volcanico.py`.
2. Cambiar el filtro de radial y los umbrales del contrato.
3. El resto del flujo (Parquet canónico, Isolation Forest, Provenance, checkpoints) reutiliza
   la misma infraestructura sin modificación.

---

## Paso 5: Añadir tests sintéticos

En `tests/test_contract.py` existe ya la función `test_generic_contract_transferable_to_volcano_example`
como plantilla. Para un dominio nuevo, añadir:

```python
def test_volcanic_contract_detects_extreme_temp() -> None:
    dates = pd.date_range("2020-01-01", periods=24, freq="MS")
    temps = [85.0] * 23 + [900.0]  # pico extremo en el último mes
    df = pd.DataFrame({"fecha_utc": dates, "temp_fumarola_c": temps, "punto": ["F01TF"] * 24})

    viols = run_generic_contract(
        df,
        col_time="fecha_utc",
        col_value="temp_fumarola_c",
        col_id="punto",
        variable_name="temperatura fumarola",
        units="°C",
        thresholds=UMBRALES_VOLCANICO,
    )
    assert any(v.code == "out_of_absolute_range" for v in viols)
```

---

## Referencia rápida: qué está en cada módulo

| Módulo | Rol |
|--------|-----|
| `src/ieo/radiales_catalog.py` | Catálogo de códigos de estación por dominio; función `identify_radial` |
| `src/ieo/validation/radial_contract.py` | Contrato específico CTD oceánico (T, S, gradientes, deriva) |
| `src/ieo/validation/generic_series_contract.py` | Capa 0: rango absoluto, duplicados, brechas, tendencia — agnóstica al dominio |
| `src/ieo/validation/__init__.py` | Punto de entrada unificado; exporta ambos contratos |
| `src/ieo/runtime/provenance.py` | Trazabilidad corrida ↔ fuente de datos |
| `run/pipeline_runs.py` | Localiza y carga corridas (sin Streamlit; apto para tests) |

---

## Lo que requiere validación científica externa (no solo código)

> El código puede ejecutarse con cualquier umbral, pero la **validación científica**
> de que esos umbrales son correctos para el dominio es responsabilidad del
> investigador experto, no del sistema de software.

| Ítem | Quién lo valida |
|------|----------------|
| Umbrales físicos (`abs_min`, `abs_max`) | Investigador del dominio |
| Interpretación de tendencia (señal vs. error de calibración) | Investigador + publicaciones de referencia |
| Política de embargo de datos | Institución (IEO, CSIC…) |
| Autorización para integrar fuentes heterogéneas | Responsable de campaña |

---

## Documentos relacionados

- [`docs/arquitectura_validacion_datos.md`](arquitectura_validacion_datos.md) — diagrama de 6 capas.
- [`docs/posicionamiento_trl.md`](posicionamiento_trl.md) — TRL, limitaciones, qué no prometer.
- [`DEMO.md`](../DEMO.md) — demo en 3 comandos.

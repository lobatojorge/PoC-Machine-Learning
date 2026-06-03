# Glosario — estaciones, Cruise y año en `.cnv`

## Estación canónica vs SeaBird

| Concepto | Origen | Uso en el visor |
|----------|--------|-----------------|
| **Estación IEO** | Códigos E1GI, E2GI, … (transecto 1–4) | Botones, series, mapa |
| **`** Station:`** SBE** | Metadato del cast en cabecera | Solo ingesta; **0** = sin asignar |
| **Carpeta `St.N CNVs`** | Histórico Cudillero | Estación **N** (1–3) |

Implementación: [`src/ieo/radial_canonical_station.py`](../src/ieo/radial_canonical_station.py).

## Localidades en `** Cruise:` (castellano y asturiano)

| Texto en Cruise (ejemplos) | Radial |
|---------------------------|--------|
| Cudillero, Radial … Cudillero | `cudillero` |
| **Cuideiru**, Asturies | `cudillero` |
| Gijón, Jureva | `gijon` |
| **Xixón** | `gijon` |
| Santander, … | `santander` |

Alias en código: `LOCALITY_ALIASES_ASTURIAN` en [`src/ieo/io/cnv_radial.py`](../src/ieo/io/cnv_radial.py).

## Auditoría

```bash
python run/audit_station_acronyms.py
python run/audit_station_acronyms.py --radial gijon
```

Salidas:

- `outputs/temporal/station_acronym_audit.csv` — un registro por fichero.
- `outputs/temporal/cruise_unique_by_radial.csv` — valores únicos de Cruise para ampliar el glosario.

Tras revisar el CSV, actualizar el mapa en `radial_canonical_station.py` y los alias en `cnv_radial.py`.

## Año de muestreo (`fecha`)

Prioridad al construir la fecha (véase `explain_sampling_year` en [`cnv_header.py`](../src/ieo/io/cnv_header.py)):

1. Carpeta **`YYYY/`** en la ruta bajo `data/cnv/` (p. ej. `…/2019/archivo.cnv`).
2. Sufijo del nombre: `apr94` → 1994, `gnov105` → 2005.
3. `# start_time =` en cabecera (a menudo año de **calibración** erróneo, p. ej. 2001 en ficheros de 2019).

El pipeline y el visor aplican `reconcile_start_time_year` antes de agregar series mensuales.

## Gijón (E1GI–E4GI)

| Código | Estación canónica |
|--------|-------------------|
| E1GI | 1 |
| E2GI | 2 |
| E3GI | 3 |
| E4GI | 4 |

Cualquier otro índice en `estacion` tras mapeo se excluye de la UI.

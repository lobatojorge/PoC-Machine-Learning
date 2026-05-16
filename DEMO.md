# Demo — IEO Orchestrator (Radial Cudillero)

Reproducir la demo completa en 3 comandos.  
Tiempo estimado: 2–5 minutos (más si el CSV es grande).

---

## Requisitos previos

| Requisito | Verificación |
|-----------|-------------|
| Python 3.11+ | `python --version` |
| CSV de entrada | `data/processed/perfiles_all.csv` (no incluido en git; solicitar al responsable del proyecto) |
| Dependencias | `pip install -r run/requirements.txt` |

> Si no tienes el CSV, puedes revisar la arquitectura del sistema directamente en el visor
> si existe una corrida previa bajo `outputs/runs/`. Pasa al paso 3.

---

## Los 3 comandos

```bash
# 1. Pipeline: ingesta → contrato de calidad → Isolation Forest → Parquet
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
├── provenance.json                          # qué CSV entró, cuándo, con qué parámetros
├── data/
│   ├── perfiles_all.ctd_canonical.parquet  # tabla canónica (todas las filas)
│   ├── perfiles_all.ctd_clean.parquet      # filas válidas según Isolation Forest
│   └── perfiles_all.ctd_anomalies.parquet  # filas segregadas (no eliminadas)
└── checkpoints/
    ├── 01_ingesta.html
    ├── 01b_contrato_radial.html             # resultado del contrato de datos
    └── 02_anomalias.html
```

---

## Qué muestra el visor

El visor (`run/app.py`) carga la corrida más reciente y presenta:

1. **Tarjetas pipeline** — estado de cada paso (ingesta, contrato, anomalías, calidad).
2. **Perfil T/S** — series T y salinidad a 5 m por estación (E1CU, E2CU, E3CU).
3. **Contrato de datos** — cualquier ERROR o WARNING del contrato radial aparece
   en rojo/ámbar _antes_ de los gráficos (el investigador ve el estado de calidad
   antes de interpretar la gráfica).
4. **Anomalías Isolation Forest** — pestaña dedicada con mapa de puntos anómalos
   vs. limpios.
5. **Hitos de serie** — min/max histórico, cobertura mensual, tendencia.
6. **FAQ** — preguntas frecuentes sobre metodología y limitaciones.

---

## Smoke test automático

```bash
# Solo verifica pipeline existente (sin relanzar main.py):
python scripts/e2e_smoke.py --skip-pipeline

# Verifica pipeline + lanza Streamlit y comprueba el endpoint de salud:
python scripts/e2e_smoke.py --with-streamlit
```

Salida esperada:
```
[e2e] OK: Parquet limpio+anomalías · run_id=... · limpias=N anómalas=M
[e2e] OK: sin WARNING ni ERROR en contrato simulado
[e2e] Smoke completado.
```

---

## Tests unitarios (sin datos IEO)

```bash
pip install -r requirements-dev.txt
pytest tests/test_contract.py tests/test_radiales_catalog.py -v
```

Los tests usan datos sintéticos: no necesitan `data/processed/perfiles_all.csv`.  
Cubren el contrato radial, el contrato genérico y el catálogo de radiales.

---

## Arquitectura en 60 segundos

```
CSV (datos campaña)
   │
   ▼  python run/main.py
[01 Ingesta]  →  Parquet canónico  →  provenance.json
   │
   ▼
[01b Contrato radial]  →  ERROR / WARNING (rangos, gradientes, deriva)
   │
   ▼
[02 Isolation Forest]  →  clean.parquet + anomalies.parquet
   │
   ▼  streamlit run run/app.py
[Visor]  →  tarjetas QC + series T/S + FAQ
```

El contrato de datos es **código Python ejecutable** (no un documento PDF),
por lo que se puede versionar, probar en CI y extender a nuevos dominios.

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| [`docs/posicionamiento_trl.md`](docs/posicionamiento_trl.md) | TRL 4, limitaciones honestas, roadmap TRL 5 |
| [`docs/arquitectura_validacion_datos.md`](docs/arquitectura_validacion_datos.md) | Diagrama de capas; cómo transferir a otro dominio |
| [`docs/contrato_datos_radiales.md`](docs/contrato_datos_radiales.md) | Reglas del contrato radial en detalle |
| [`docs/domain_catalog.md`](docs/domain_catalog.md) | Cómo añadir un nuevo dominio / campaña al sistema |
| [`docs/guion_reunion_eugenio.md`](docs/guion_reunion_eugenio.md) | Pitch 3 minutos para colaboradores |
| [`docs/operacion_tfm.md`](docs/operacion_tfm.md) | Operación, Docker, alcance TFM |

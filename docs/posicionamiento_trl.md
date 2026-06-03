# Posicionamiento TRL — IEO Orchestrator

Documento de referencia para reuniones con stakeholders (p. ej. investigadores CSIC, colaboradores en otros dominios). Resume **capacidades actuales**, **potencialidades** con expectativas alineadas, el **TRL**, las **limitaciones** (clasificadas por origen), **debilidades** y un **roadmap** realista hacia TRL 5.

---

## Índice práctico

| Necesidad en reunión | Sección |
|----------------------|---------|
| Mensaje ejecutivo corto | [Mensaje en una frase](#mensaje-en-una-frase) |
| Qué cotizar / qué demos hoy puede mostrar sin magia | [Capacidades actuales](#capacidades-actuales-qué-puede-hacer-hoy) |
| Qué venderías al IEO pero no existe aún instalado | [Potencialidades](#potencialidades-valor-futuro-honesto) |
| Por qué no es TRL 5 ya | [Por qué aún no es TRL 5](#por-qué-aún-no-es-trl-5) y [Limitaciones por origen](#limitaciones-por-origen-tabla-para-reunión) |

## Mensaje en una frase

El entregable no es solo una gráfica de una radial: es una **arquitectura reproducible** para que perfiles CTD (`.cnv`) pasen por ingesta, contrato de calidad, segregación de anomalías, análisis temporal con validación holdout y un visor con trazabilidad — hoy demostrado con **todas las radiales Cantábrico en pipeline** y **presentación priorizada en Gijón** en el visor.

---

## Capacidades actuales (qué puede hacer hoy)

| Ámbito | Capacidad | Dónde se ve |
|--------|-----------|--------------|
| **Ingesta y control previo** | Comprobaciones mínimas por fichero SeaBird antes de entrar en el pipeline; cuarentena con motivos escritos (`reasons.json`) | `src/ieo/ingest_gate.py`, `data/quarantine/` |
| **Normalización nominal** | Mismo vocabulario de columnas (fecha, estación, profundidad, T, S…) para todas las fuentes procesadas | Esquema canónico + Parquet por corrida |
| **Contrato de dominio** | Reglas con severidad ERROR / WARNING (rangos físicos, fechas coherentes, saltos en perfil y en serie mensual, deriva opcional); en visor ERROR bloquea gráfica hasta diagnóstico explícito | `radial_contract.py`, `docs/contrato_datos_radiales.md` |
| **Observabilidad estadística** | Filas marcadas como atípicas **segregadas** (`*_ctd_anomalies.parquet`) con auditoría; dataset limpio explícito | `pipeline_qc.py`, `outputs/runs/` |
| **Análisis con holdout honesto** | Marcos + bandas iid sobre residuos; **último mes con observación** fuera del ajuste para pronóstico | `atac_monthly_report.py` |
| **Multi‑radial en pipeline** | La misma cadena QC + Parquet puede aplicarse a todas las radiales clasificables o acotarse por `IEO_PIPELINE_RADIAL` | `README.md`, consola / `run_summary.json` |
| **Visor Gijón (demo)** | Capa «early warning»: hero, embudo narrado (pasos sin jerga de herramientas), mapas Cantábrico + transecto como contexto visual, **botones por estación** (E1GI–E4GI), banners de provenance con cifras; carga preferente de Parquet de la corrida también para **Gijón** (no solo lectura intensiva de `.cnv`) | `run/app.py`, `run/viewer_presentation.py` |
| **Rendimiento en demo** | Carga de datos antes de dibujar mapas Plotly; sin selección redundante por clic que fuerce rerun completo solo por interaccionar | `run/app.py` |
| **Reproducibilidad** | Corrida identificada, `provenance.json`, checkpoints HTML y `outputs/RESUMEN_ULTIMA.html`; smoke E2E opcional | `DEMO.md` |
| **Portabilidad de ideas** | Contrato genérico de serie (`generic_series_contract.py`), informes Plotly fuera de Streamlit (`figures_radiales.py`) | `docs/domain_catalog.md` |

Estas capacidades pueden **cotizarse**: número de ficheros en cuarentena, filas con ERROR de contrato, filas marcadas como anomalías vs limpias, rango temporal cubierto, última campaña, tiempo de corrida por paso — sin depender de «confianza ciega».

---

## Potencialidades (valor futuro honesto)

| Potencialidad | Para qué sirve | Qué falta típicamente (no es código) |
|---------------|----------------|---------------------------------------|
| **URL estable / piloto institucional** | Eugenio u otro equipo abre siempre la misma demo sin instalar Python | TI: VM, HTTPS, runbook (`integracion_web_ieo.md`) |
| **Orquestación tras campaña** | Nuevo `.cnv` llega → pipeline automático → resumen correo/dashboard | Cron, disco compartido, acuerdo con buque/datacenter |
| **Gobernanza de datos** | Embargo por campaña, roles lectura/publicación | Políticas IEO, autenticación |
| **Otras radiales como primera pantalla en visor** | Misma UX que Gijón; botones de ciudad + Parquet ya filtran por `radial_id` | Diseño producto / tiempo de UX; contenido metodología por radial |
| **Profundidades 20 m / 50 m** | Serie y contrato paralelos ya planteados en UI como «próximamente» | Validación científica de umbrales y copy |
| **Export estático interoperable** | Paquete HTML Plotly por radial o snapshot para stakeholder sin Streamlit | Script de empaquetado (trabajo menor frente al core ya separado Plotly/UI) |
| **Integración con catálogo corporativo** | Great Expectations, OpenLineage, etc. solo si institución lo exige | Presupuesto y estándares TI |
| **Otros dominios y sensores** | Mismo embudo para sensores agua/aire/volcanología. A futuro: **Boyas Euro-Argo** (perfiladores deriva) y **Landpicker** (amarres fijos). | Experto dominio + `domain_catalog.md` (requiere adaptar validación a datos no-radiales) |

**Mensaje de venta sobrio:** el repositorio demuestra el **patrón de auditoría** y **métricas medibles en cada paso**; cerrar TRL 5 depende menos de reinventar ingeniería y más de **operación institucional y datos en flujo estable**.

---

## Nivel TRL actual: **4** (defendible)

| Nivel | Significado (datos / software) | Estado |
|-------|-------------------------------|--------|
| TRL 3 | Prueba de concepto con datos reales, flujo manual | Superado |
| **TRL 4** | Validado en entorno relevante: pipeline reproducible + datos reales + demostrador que consume salidas validadas | **Hoy** |
| TRL 5 | Validado en entorno operativo representativo (servidor institucional, operador no desarrollador) | Objetivo próximo |
| TRL 6 | Demostración con usuarios reales en operación rutinaria | Medio plazo |
| TRL 7+ | Producción institucional integrada (web IEO, SLA, gobernanza) | Fuera del alcance TFM inmediato |

### Evidencias TRL 4 en este repositorio

- Corridas versionadas bajo `outputs/runs/<run_id>/` con `provenance.json` y `run_summary.json` (salida estructurada JSON).
- Parquet limpio y de anomalías (`*.ctd_clean.parquet`, `*.ctd_anomalies.parquet`).
- **Control previo de ficheros** (`src/ieo/ingest_gate.py`): comprobación antes de ingestar; ficheros rechazados se copian a `data/quarantine/` con `reasons.json`.
- Contrato de datos en código: `src/ieo/validation/radial_contract.py` (ERROR / WARNING antes del análisis en visor).
- Detección multivariante (Isolation Forest, `contamination=0.05` por estrato); anomalías segregadas, no eliminadas silenciosamente.
- Modelo Marcos con holdout y bandas iid interpretables, sin AR (`src/atac_monthly_report.py`).
- Clasificación `.cnv` por coordenadas y metadatos (`src/ieo/io/cnv_radial.py`); alias asturiano en cruise (`Xixón`/`Cuideiru`).
- Visor orientado a **presentación estable**: sidebar oculto, hero «early warning», franja de embudo narrado (`run/viewer_presentation.py`), mapas Plotly Cantábrico + transecto como **contexto** (sin depender del clic como paso pesado).
- Preferencia por **Parquet de la corrida seleccionada** también para radial **gijon** (lectura rápida); fallback a `.cnv` clasificados si falta corrida útil — ver `docs/visor_radiales.md`.
- **Estaciones** mediante botones consistentes (`E1GI`–`E4GI`): estación inicial con datos cargada sin paso previo obligatorio sobre el mapa.
- Series T/S @ 5 m con FAQ contextual, banners de fuente/fechas y alertas contrato debajo de gráfica cuando aplica (no sustituye informe científico firmado).
- Demo: **solo Gijón** en primera pantalla narrativa (`radial_id` fijo a la demo); holdout de **un solo mes** (último con observación); agregación mensual con el **lance más profundo** del mes si hay varios CTD.
- Funciones de gráficas desacopladas del framework en `src/ieo/reports/figures_radiales.py` (Plotly puro, sin Streamlit); export puntual HTML de series auxiliar (`temporal_series_export.py`).
- Ingesta incremental (`pipeline_manifest.json`, `artifact_cache/`), QC paralelo y consola estructurada.

### Por qué aún no es TRL 5

- Despliegue en Streamlit local o demo; no servicio operado por el IEO con procedimiento formal ni URL estable.
- Sin autenticación, embargos de campaña ni acuerdo TI para integración web (ver `docs/integracion_web_ieo.md`).
- Operación depende de un técnico que ejecute el pipeline manualmente; sin orquestación ni SLA institucional.
- Capa de análisis y UX más revisada en **Gijón** que en el resto de radiales del visor (misma cadena de datos en pipeline).

---

## Limitaciones por origen (tabla para reunión)

Usar esta tabla para no mezclar **falta de financiación / recursos institucionales** con **decisiones metodológicas** o **carga de trabajo del TFM**.

| Origen | Qué significa en este proyecto | Ejemplos concretos |
|--------|--------------------------------|-------------------|
| **Financiación / recursos institucionales** | Requiere presupuesto, personal TI, infra o acuerdo formal que el TFM no tiene | Servidor IEO con URL estable; login y embargos; integración en web RADIALES; cron/Airflow; formación masiva de operadores; Great Expectations corporativo; modelos profundos (TimeGPT) con GPU; profundidades 20/50 m activas en producto; metodología escrita por radial (solo Cudillero está completa en markdown) |
| **Metodología / ciencia** | Decisiones de diseño del modelo o del contrato; corregibles con criterio científico, no solo con dinero | Marcos + residuos **iid** (sin AR); holdout de **1 mes** (no 12); IF como capa estadística **adicional** al contrato físico; interpolación lineal a 5 m; un valor mensual = lance **más profundo** del mes (heurística operativa); clasificación radial por geo/cruise (casos límite Coruña/Gijón); métricas del visor = **diagnóstico**, no certificación para publicación |
| **Carga de trabajo / alcance TFM** | Deuda técnica o alcance temporal de una persona en un máster | Streamlit como demostrador, no portal definitivo; pipeline manual `python run/main.py`; corridas largas (~3500 `.cnv`); tests sin batería de `.cnv` reales en CI; variantes de cabecera SBE aún parciales; pulido de UI centrado en demo Gijón |

### Detalle: financiación / institución

- **Despliegue operativo:** sin máquina ni procedimiento del IEO que sustituya «ejecutar en el portátil del TFM».
- **Gobernanza de datos:** sin catálogo corporativo, embargos por campaña ni roles (investigador vs público).
- **Integración web:** opciones documentadas en `integracion_web_ieo.md`; dependen de TI y prioridad del programa RADIALES.
- **Automatización:** sin job nocturno que ingiera nuevos `.cnv` del buque y notifique cuarentena.
- **Producto completo:** 20 m y 50 m deshabilitados en UI; documentación de campo por radial incompleta fuera de Cudillero.

### Detalle: metodología / ciencia

- **Modelo temporal:** tendencia + Fourier mensual (Marcos); incertidumbre con σ constante sobre residuos. Es **interpretable**, no el estado del arte en pronóstico oceánico.
- **Validación:** el último mes con dato se reserva para pronóstico (no entra en el ajuste). Es una comprobación honesta, no un informe de validación cruzada multi-año.
- **Calidad:** `radial_contract` + Isolation Forest; el investigador sigue siendo responsable de revisar instrumental, post-procesado SeaBird y contexto de campaña.
- **Agregación:** si hay dos rosetas en el mismo mes, se toma el perfil que alcanzó **mayor profundidad** (evita mezclar un lance superficial con uno de agua de botella).

### Detalle: carga de trabajo / alcance TFM

- **Un desarrollador, un entorno:** prioridad en cerrar demo reproducible (pipeline + visor Gijón) frente a endurecer todas las radiales en UI.
- **Rendimiento:** paso 02 (contrato + IF por perfil) domina el tiempo; mitigado con caché incremental y paralelismo, no con cluster.
- **Pruebas:** pytest con datos sintéticos; smoke E2E opcional; sin regresión automática sobre el archivo completo del IEO en cada PR.

---

## Debilidades actuales y mejoras priorizadas

| Debilidad | Mejora natural | Origen principal |
|-----------|----------------|------------------|
| Visor solo en local / sin SLA | Piloto en VM IEO + URL + runbook | Financiación / TI |
| Mensajes y textos aún técnicos en algunas rutas | Revisión con usuario final (oceanógrafo) | Carga TFM |
| Clasificación radial errónea en casos raros | Auditoría `audit_cnv_radials.py` + reglas en catálogo | Metodología + carga |
| Corrida completa lenta | Solo incremental en operación; `IEO_PIPELINE_RADIAL` en pruebas | Carga (mitigado en código) |
| Sin AR en residuos | Documentado; añadir AR solo si el comité lo exige | Metodología |
| Contrato no es Great Expectations | Migración GX si TI lo impone | Financiación / institución |
| Metodología markdown solo Cudillero | Plantilla `metodologia_radiales_<id>.md` por radial | Carga TFM |
| UI solo **Gijón** en modo presentación frente al pipeline multi-radial «completo» | Reactivar selección ciudad con botones o recuperar clic mapa cuando el producto pida multisitio estable | Producto |

---

## Limitaciones resumidas (lenguaje de reunión)

Presentarlas como **alcance y transparencia**, no como excusas.

### Datos y dominio

- Pipeline: **todas** las radiales clasificables en `data/cnv/`; **visor de reunión**: solo radial **gijon** como narrativa inicial (los Parquet multi-radial sirven igual para otras cuando se amplíe la UI).
- Ingesta de producción: **`.cnv`** (SeaBird); CSV legacy solo en scripts antiguos.
- Profundidades 20 m y 50 m: previstas en UI, no activas.
- Mezcla histórica de radiales: mitigada por catálogo y filtro en visor; exige disciplina al copiar datos del buque.
- **Fuentes futuras (Euro-Argo / Landpicker)**: El orquestador es agnóstico en su core (Ingesta → Contrato → Anomalías), pero requerirá el desarrollo de reglas de dominio específicas (ya que Euro-Argo carece de estaciones fijas al estar a la deriva, y Landpicker emite series temporales fijas, no perfiles verticales).

### Calidad y ciencia

- Contrato propio en Python (no GX por defecto).
- IF: detección multivariante; no sustituye juicio del investigador.
- Holdout 1 mes y gráfico con marcadores (sin polilíneas entre campañas): legibilidad para demo; el comité puede pedir otro diseño.

### Producto y operación

- Streamlit = demostrador; no portal web institucional.
- Sin login ni embargos.
- Pipeline manual; sin orquestación en producción.

### Repositorio

- Código activo: `src/ieo/`, `src/02_analysis.py`, `src/atac_monthly_report.py`, `run/`. Scripts históricos Excel/Gijón fuera del árbol.

---

## Arquitectura transferible (otros dominios)

Ver diagrama detallado en [`docs/arquitectura_validacion_datos.md`](arquitectura_validacion_datos.md).

| Capa | Rol | Ejemplo en otro dominio |
|------|-----|-------------------------|
| Ingesta canónica | Esquema común + readers | Series de sensores volcánicos → tabla estándar |
| Provenance | Trazabilidad corrida ↔ fuente | Campaña ↔ versión procesada |
| Contrato de datos | Reglas + ERROR/WARNING | Umbrales físicos y consistencia temporal |
| Observabilidad | Anomalías + auditoría | IF o reglas + cuarentena |
| Análisis validado | Modelo + holdout | Tendencia / estacionalidad con bandas |
| Visor gobernado | Exploración con QC visible | No confundir fallo de dato con señal natural |

---

## Objetivos de escalamiento (O1–O6)

| ID | Objetivo | Plazo orientativo | TRL |
|----|----------|-------------------|-----|
| O1 | Narrativa TRL + clasificación de limitaciones (este doc, README) | Hecho (TRL 4) | 4 |
| O2 | Demo reproducible (`main.py` → Parquet → `app.py`; smoke; incremental) | Hecho | 4 |
| O3 | Visor presentación Gijón + pipeline multi-radial | Hecho | 4 |
| O3b | Velocidad de demo visor + Parquet multi‑radial + botones estación sin reruns pesados por mapa | Hecho | 4 |
| O4 | Piloto desplegado (URL estable) + runbook operador | 2–4 semanas (**TI / financiación**) | 5 |
| O5 | Gobernanza: embargos, metodología por radial, evolución contrato | Paralelo (**institución**) | 5–6 |
| O6 (opc.) | Demo compartida estática (`RESUMEN_ULTIMA.html` + opcional paquete HTML Plotly por radial / Streamlit Cloud con subconjunto) | Depende alcance reuniones (**carga**) | 4→5 soporte comunicación |

---

## Qué no prometer

- Despliegue de todas las radiales españolas en el visor a corto plazo.
- Sustituir informes científicos o el portal oficial del proyecto RADIALES.
- Great Expectations “ya integrado”.
- Producto listo para público general sin supervisión científica.

---

## Great Expectations

**Decisión:** no es requisito para TRL 4 ni para la reunión inminente. El módulo `radial_contract` cumple el papel de “expectativas” codificadas. Migrar a GX implica 1–2 semanas mínimo de reingeniería y doble mantenimiento si no se retira el contrato actual.

---

## Documentos relacionados

- [`DEMO.md`](../DEMO.md) — secuencia mínima pipeline → smoke → visor.
- [`visor_radiales.md`](visor_radiales.md) — comportamiento actual del Streamlit (`run/app.py`).
- [`guion_reunion_eugenio.md`](guion_reunion_eugenio.md) — guion 3 min y tablas para la reunión.
- [`arquitectura_validacion_datos.md`](arquitectura_validacion_datos.md) — diagrama de capas.
- [`integracion_web_ieo.md`](integracion_web_ieo.md) — opciones y preguntas para TI del IEO.
- [`contrato_datos_radiales.md`](contrato_datos_radiales.md) — reglas implementadas.
- [`operacion_tfm.md`](operacion_tfm.md) — operación, Docker, alcance TFM.

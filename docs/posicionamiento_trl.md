# Posicionamiento TRL — IEO Orchestrator

Documento de referencia para reuniones con stakeholders (p. ej. investigadores CSIC, colaboradores en otros dominios). Describe el **nivel de madurez actual**, las **limitaciones** y un **roadmap** realista hacia TRL 5.

---

## Mensaje en una frase

El entregable no es solo una gráfica de la radial de Cudillero: es una **arquitectura reproducible** para que datos de campaña pasen por ingesta, contrato de calidad, segregación de anomalías, análisis temporal con validación y un visor que deja trazabilidad — aplicable a otras series temporales (CTD, sensores, volcanología).

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

- Corridas versionadas bajo `outputs/runs/<run_id>/` con `provenance.json`.
- Parquet limpio y de anomalías (`*.ctd_clean.parquet`, `*.ctd_anomalies.parquet`).
- Contrato de datos en código: `src/ieo/validation/radial_contract.py` (ERROR / WARNING antes del análisis en visor).
- Detección multivariante (Isolation Forest); anomalías segregadas, no eliminadas silenciosamente.
- Modelo Marcos + ATAC con holdout y bandas interpretables (`src/atac_monthly_report.py`).
- Visor Streamlit con tarjetas de calidad, hitos de serie, FAQ y avisos de contexto (no sustituye informe científico firmado).

### Por qué aún no es TRL 5

- Despliegue en Streamlit local o demo; no servicio operado por el IEO con procedimiento formal.
- Entrada principal aún en transición CSV → `.cnv` como única vía de producción.
- Un producto profundo (Cudillero, T/S @ 5 m), no plataforma multi-campaña operada por terceros sin formación.
- Sin autenticación, embargos de campaña ni acuerdo TI para integración web (ver `docs/integracion_web_ieo.md`).

---

## Limitaciones (decirlas en reunión)

Presentarlas como **decisiones de alcance del TFM**, no como excusas.

### Datos y dominio

- Caso demostrado en profundidad: **Cudillero** (E1CU–E3CU), con filtro por catálogo (`src/ieo/radiales_catalog.py`).
- Formato de ingesta en práctica: CSV tabular; lectores `.cnv` en roadmap.
- Profundidades 20 m y 50 m: previstas en UI, no activas en la demo actual.
- Riesgo histórico de mezcla de radiales en fuentes heterogéneas: mitigado por catálogo; exige disciplina de ingesta.

### Calidad y ciencia

- **Contrato de datos propio** (Python), no Great Expectations: mismas ideas (expectativas, severidad), distinta herramienta. Integrable a GX en fase institucional si TI lo exige.
- Isolation Forest: detección estadística multivariante; la validación física exhaustiva sigue siendo responsabilidad del investigador.
- Métricas del visor (cobertura %, holdout fuera de banda): **diagnóstico**, no certificación para publicación.

### Producto y operación

- Streamlit = demostrador ágil, no portal web institucional definitivo.
- Concurrencia y SLA no garantizados; sin login.
- Pipeline lanzado manualmente (`python run/main.py`); sin orquestación programada (cron/Airflow) en producción.

### Repositorio

- Legado Gijón (scripts `00_*`, Excel) convive con pipeline `src/ieo/`; la demo oficial es Cudillero vía `run/main.py` + `run/app.py`.

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

## Objetivos de escalamiento (O1–O5)

| ID | Objetivo | Plazo orientativo | TRL |
|----|----------|-------------------|-----|
| O1 | Narrativa y TRL documentados; README alineado con stack real | 2–3 días | 4 |
| O2 | Demo única reproducible (`main.py` → Parquet → `app.py`; smoke test) | 1 semana | 4 |
| O3 | Arquitectura genérica documentada; contrato desacoplado del visor | 1 semana | 4→5 |
| O4 | Piloto desplegado (URL estable) + ingesta `.cnv` documentada | 2–4 semanas (TI) | 5 |
| O5 | Gobernanza: catálogo de dominio, embargos, evolución del contrato (sin GX obligatorio) | Paralelo | 5–6 |

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

- [`guion_reunion_eugenio.md`](guion_reunion_eugenio.md) — guion 3 min y tablas para la reunión.
- [`arquitectura_validacion_datos.md`](arquitectura_validacion_datos.md) — diagrama de capas.
- [`integracion_web_ieo.md`](integracion_web_ieo.md) — opciones y preguntas para TI del IEO.
- [`contrato_datos_radiales.md`](contrato_datos_radiales.md) — reglas implementadas.
- [`operacion_tfm.md`](operacion_tfm.md) — operación, Docker, alcance TFM.

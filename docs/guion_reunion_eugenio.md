# Guion reunión — Eugenio (y colaboradores)

Duración orientativa: **3 minutos** de pitch + tiempo para preguntas. Complementa [`posicionamiento_trl.md`](posicionamiento_trl.md) y [`arquitectura_validacion_datos.md`](arquitectura_validacion_datos.md).

---

## Guion (3 min)

### 1. Problema (30 s)

Los datos de campaña acaban en gráficas sin un **embudo de confianza común**: no queda claro qué pasó por validación, qué se segregó como anómalo y qué es variabilidad natural del sistema. Eso dificulta auditar series antes de publicarlas o compararlas entre campañas.

### 2. Solución — arquitectura en 6 capas (60 s)

Mostrar diagrama en `docs/arquitectura_validacion_datos.md`:

1. Ingesta a esquema canónico  
2. Provenance por corrida  
3. Contrato de datos (ERROR / WARNING)  
4. Observabilidad (anomalías segregadas)  
5. Análisis temporal con holdout (Marcos + ATAC)  
6. Visor que explica calidad, no solo dibuja líneas  

**Demo:** radial Cudillero (IEO), temperatura y salinidad a 5 m, tres estaciones. **TRL 4:** funciona con datos reales en entorno de laboratorio / demo, reproducible con `python run/main.py` y `streamlit run run/app.py`.

### 3. Limitaciones — cuatro bullets (45 s)

| Bloque | Mensaje corto |
|--------|----------------|
| Datos | Un caso profundo (Cudillero); CSV hoy, `.cnv` en camino; no es plataforma nacional de radiales aún |
| Ciencia | Contrato Python propio (no GX); IF para atípicos; el visor no certifica informes |
| Producto | Streamlit = demostrador; integración web IEO pendiente de TI |
| Alcance TFM | Patrón reutilizable; la gráfica concreta es la prueba, no el producto final |

### 4. Transferencia a otros dominios (30 s)

El mismo patrón aplica a **series temporales de volcanes, sensores o campañas repetidas**: catálogo de estaciones, reglas de rango y consistencia, segregación de outliers, modelo con validación cruzada temporal, visor con métricas de confianza. El entregable es el **patrón de auditoría**, no solo el Cantábrico.

### 5. Siguiente paso (15 s)

- **2 semanas:** demo reproducible + documentación TRL (O1–O2).  
- **Trimestre:** piloto en URL estable + ingesta `.cnv` si TI responde (TRL 5).  
- **No prometemos:** todas las radiales, GX integrado, portal IEO definitivo mañana.

---

## Tabla: limitaciones vs mensaje para Eugenio

| Limitación técnica | Cómo decirlo sin debilitar el proyecto |
|--------------------|--------------------------------------|
| Solo Cudillero en demo | “Profundizamos un caso para validar la arquitectura antes de escalar radiales” |
| Streamlit | “Demostrador rápido; la arquitectura no depende de Streamlit” |
| Sin Great Expectations | “Expectativas codificadas en contrato Python; GX es opción institucional futura” |
| IF no es verdad física | “Capa de alerta multivariante; el científico decide” |
| TRL 4, no 5 | “Validado en laboratorio con datos reales; siguiente paso es servidor IEO” |

---

## Tabla: objetivos O1–O5 (escalamiento justificado)

| ID | Objetivo | Por qué | Plazo |
|----|----------|---------|-------|
| O1 | Documentar TRL + limitaciones + README honesto | Alinear narrativa con código | 2–3 días |
| O2 | Una ruta demo: pipeline → visor + smoke test | Reproducibilidad ante terceros | 1 semana |
| O3 | Arquitectura genérica documentada | Vender patrón a Canarias / otros grupos | 1 semana |
| O4 | URL estable + `.cnv` en piloto | TRL 5 | 2–4 semanas |
| O5 | Gobernanza (catálogo, embargos, contrato) | Escalamiento institucional | Paralelo |

---

## Demo en vivo (checklist)

1. `cd run` · `pip install -r requirements.txt` (si hace falta).  
2. `python main.py` (o mostrar corrida existente en `outputs/runs/`).  
3. `streamlit run app.py` → Cudillero → E1CU → Temperatura.  
4. Señalar: tarjetas de calidad, gráfica, hitos, FAQ, aviso ámbar de contrato.  
5. Mencionar: “no sustituye informe firmado”.

Smoke automatizado: `python scripts/e2e_smoke.py --skip-pipeline` (si ya hay corrida).

---

## Preguntas que pueden surgir

**¿Por qué no Great Expectations?**  
Mismo rol conceptual; implementación a medida para reglas oceanográficas (perfiles, Δz, serie mensual). GX añadible si el IEO lo exige operativamente.

**¿Se puede usar en Canarias / volcanes?**  
Sí a nivel de arquitectura: catálogo + contrato + pipeline + visor. Hay que definir esquema canónico y umbrales del dominio.

**¿Está en la web del IEO?**  
No aún; opciones en `integracion_web_ieo.md`; requiere TI (iframe, subdominio o HTML estático a largo plazo).

**¿TRL?**  
4 hoy; 5 con despliegue y operador no desarrollador.

---

## Qué llevar impreso o en pantalla

1. Diagrama: `arquitectura_validacion_datos.md`  
2. Tabla TRL: `posicionamiento_trl.md`  
3. URL o capturas del visor (tema oscuro, tarjetas pipeline visibles)

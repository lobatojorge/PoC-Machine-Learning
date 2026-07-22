# Resumen Ejecutivo del Proyecto (IEO Orchestrator)

Este documento explica de forma sencilla y directa el estado actual del sistema, sus capacidades reales, sus límites y los siguientes pasos lógicos para llevarlo a un entorno de producción oficial.

---

## 1. ¿Qué hace el proyecto? (Capacidades Actuales)

El sistema automatiza el proceso por el cual los datos crudos recogidos en el mar se convierten en información fiable y visualizable. En resumen, actúa como un "filtro de calidad" automatizado:

*   **Ingesta automática y control de calidad:** Lee los archivos generados por los sensores en el mar (`.cnv`). Antes de aceptarlos, verifica que los datos tengan sentido (por ejemplo, que las temperaturas o profundidades no sean físicamente imposibles).
*   **Aislamiento de errores:** Si un archivo o un dato es defectuoso, no rompe el sistema ni se borra en secreto. Se pone en "cuarentena" con una etiqueta clara del motivo, para que un especialista lo revise.
*   **Estandarización:** Convierte todos los datos a un formato único, rápido y ordenado, facilitando su lectura sin importar de qué campaña provengan.
*   **Visor de datos interactivo:** Incluye una aplicación visual donde se pueden ver las gráficas de las estaciones, mostrando claramente qué datos son correctos y cuáles tienen advertencias.

## 2. ¿Qué NO hace el proyecto? (Limitaciones)

Para mantener unas expectativas realistas, es fundamental entender lo que el sistema **no** incluye en su versión actual:

*   **No reemplaza el criterio científico:** El sistema detecta anomalías estadísticas, pero un investigador debe tomar la decisión final sobre si un dato raro es un error del sensor o un fenómeno natural real.
*   **No está accesible en internet para todo el mundo:** Actualmente funciona como una demostración local ("demo"). No tiene una página web pública (`URL`) oficial del IEO, ni un sistema de usuarios con contraseñas.
*   **No procesa datos automáticamente en tiempo real:** Requiere que una persona inicie el proceso. No está conectado directamente a los barcos para procesar datos vivos de forma autónoma.
*   **No muestra todas las zonas en el visor principal:** Aunque el motor central procesa datos de diferentes campañas, la pantalla visual está diseñada y optimizada para mostrar a la perfección la zona de Gijón a modo de demostración prioritaria.

## 3. ¿Por qué se ha hecho así? (Motivos)

Las decisiones del proyecto se han basado en crear una base sólida y confiable antes de añadir "adornos" técnicos:

*   **Prioridad en la fiabilidad de los datos:** Se ha invertido el esfuerzo en garantizar que ningún dato erróneo pase desapercibido. Es preferible tener una interfaz más sencilla pero con datos rigurosamente auditados, que una web espectacular con gráficas engañosas.
*   **Independencia y trazabilidad:** Cada paso del proceso deja un registro ("log") claro. Si algo falla, se sabe exactamente dónde y por qué. No hay procesos ocultos ("cajas negras").
*   **Alcance actual (TRL 4):** Al ser una fase de validación técnica, se ha priorizado demostrar que la lógica funciona con datos reales, dejando para la siguiente fase los requisitos de infraestructura institucional y servidores de la administración pública.

## 4. Objetivos de Escalamiento (O1–O6) — Auditoría 2026

| ID | Objetivo | Tecnología target | Criterio de éxito |
|----|----------|------------------|-------------------|
| O1 | **Orquestación compilada:** sustituir agentes generalistas por micro-agentes estrictamente tipados, compilados con Mypyc/Cython. | Micro-agentes compilados (Mypyc ≥ 0.930) | Zero `Any` en firmas críticas; pipeline ejecuta sin GIL en subproceso dedicado |
| O2 | **Inferencia local de series temporales:** eliminar dependencia de APIs externas (TimeGPT). Desplegar modelos distilados WASM para procesamiento en edge. | WASM Time Series (ONNX → wasmtime) | Latencia p99 < 200 ms en CPU estándar; cero llamadas de red en modo offline |
| O3 | **Datos espaciales dinámicos:** actualizar GNNs estáticos a Temporal Graph Networks (TGN) para modelar corrientes oceánicas 3D continuas. | PyG `TemporalData` + TGN (torch-geometric ≥ 2.5) | TGN entrenado y validado sobre campo vectorial de corrientes del Cantábrico; RMSE < baseline GNN estático |
| O4 | **Contratos de datos declarativos:** implementar Data Contracts as Code en YAML/TOML ejecutados nativamente en Polars; retirar toda dependencia de Great Expectations. | Polars `LazyFrame` + contratos YAML/TOML | 100 % de reglas de validación expresadas en contrato declarativo; zero imports `great_expectations` |
| O5 | **Zero-Copy Lakehouse:** consolidar la arquitectura OLTP → ETL → OLAP sobre Polars/Parquet con lectura en zero-copy (memory-mapped). | Polars `scan_parquet` + Apache Arrow IPC | Eliminación total de `.to_pandas()` en el path crítico; peak RAM < 512 MB en full-radial run |
| O6 | **Despliegue institucional cerrado:** empaquetar el sistema como producto software cerrado y auditable con hash-signing de artefactos y control de acceso por rol. | Docker + SLSA Level 2 + RBAC JWT | Pipeline reproducible bit-a-bit; artefactos firmados verificables por SHA256 + firma GPG |

---

## 5. Estimación de Costes y Necesidades

- **Infraestructura:** servidor seguro + almacenamiento a largo plazo; integrable en convenios institucionales existentes o coste nube bajo-medio.
- **Ingeniería TI/Sistemas:** 2–4 semanas para integración en red interna, dominios, proxy y certificados.
- **Desarrollo de Producto:** 1–2 meses para O1–O6, sistema de roles (RBAC) e interfaz multi-radial completa.
- **Mantenimiento (SLA):** revisión periódica de dependencias compiladas y modelos WASM distilados.

---

## 6. Decisión Arquitectónica: Rechazo Formal de Great Expectations

> **ADR-2026-01 — REJECTED: Great Expectations**

| Criterio | Evaluación |
|----------|------------|
| **Acoplamiento** | GE introduce un grafo de dependencias pesado (SQLAlchemy, Jinja2, jsonschema) incompatible con el principio Zero-Copy Lakehouse. |
| **Paradigma** | GE opera sobre `pandas.DataFrame` mediante expectation suites imperativas; incompatible con `Polars LazyFrame` y el plan de ejecución diferido. |
| **Mantenibilidad** | Los JSON Suites no son code-reviewables de forma quirúrgica; violan el principio de contratos como código fuente versionable (YAML/TOML). |
| **Alternativa adoptada** | `src/ieo/validation/radial_contract.py` + contratos declarativos YAML/TOML ejecutados nativamente en Polars (Objetivo O4). |
| **Estado** | ❌ Formalmente rechazado. Prohibida su reintroducción sin nueva ADR aprobada. |

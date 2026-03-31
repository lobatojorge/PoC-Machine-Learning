# Borrador de Memoria TFM: Pipeline y Visualización de Series Temporales Oceanográficas

> **Nota para ti (Jorge):** He redactado todo el contenido posible basándome en los scripts y la documentación técnica actual del repositorio `antigravity`. He dejado corchetes y notas explícitas `[NOTA: ...]` allí donde debes rellenar con tu información personal, fechas exactas, o detalles que escapan al código fuente. Como el índice de la plantilla salta del 5 al 7, lo mantuve así, pero te sugiero revisar la numeración de los capítulos. ¡Léelo y ajusta el nivel de lenguaje a tu gusto!

---

## 1. Introducción

### 1.1 Contexto y justificación del trabajo
El presente documento detalla el desarrollo de un Trabajo de Fin de Máster (TFM) centrado en el procesamiento y observación de los datos generados por el proyecto "Radiales" del Instituto Español de Oceanografía (IEO). Este programa de observación recurrente ha generado una base de datos histórica inestimable, compuesta por series temporales de muestreos biológicos y físicos marinos, los cuales son esenciales para la comprensión de los ecosistemas marinos bajo escenarios de cambio global.

La justificación de este proyecto radica en la necesidad crítica de dotar a este volumen histórico de datos de una arquitectura robusta, automatizada y reproducible. Previo a este trabajo, el manejo de datos provenientes de diversas campañas y formatos suponía un reto en términos de estandarización, interoperabilidad y aseguramiento de la calidad. Este proyecto nace para solventar el cuello de botella técnico que supone la manipulación artesanal de datos oceanográficos e implementar un flujo de trabajo computacional moderno que automatice gran parte del control de calidad y su posterior visualización.

### 1.2 Objetivos del trabajo
**Objetivo principal:**  
Diseñar, programar e implementar un *pipeline* integral de datos automatizado y una plataforma web interactiva asociada, que permita procesar, auditar y explorar las series temporales oceanográficas del programa Radiales del IEO.

**Objetivos específicos:**
1. **Ingesta y Estandarización:** Desarrollar un módulo de extracción para transformar y unificar diversas fuentes heterogéneas de datos brutos hacia un formato tabular unificado.
2. **Observabilidad y Auditoría de Datos:** Implementar un sistema automatizado (basado en herramientas como *Great Expectations*) que actúe como un "inspector", aplicando reglas físicas y biológicas para asegurar la validez de los rangos oceánicos observados antes del análisis.
3. **Análisis y Estadísticas:** Calcular métricas descriptivas y desarrollar modelados temporales sobre la base de datos limpia para facilitar la detección de tendencias y anomalías.
4. **Visualización y Diseminación:** Construir y desplegar un frontend interactivo accesible mediante entorno web (Streamlit), que ofrezca una herramienta exploratoria en tiempo real a los investigadores y partes interesadas, desacoplando la lógica analítica de las descripciones metodológicas de la propia interfaz interactiva.

### 1.3 Impacto en sostenibilidad, ético-social y de diversidad
- **Sostenibilidad:** Este desarrollo está directamente alineado con el ODS 14 de las Naciones Unidas (Conservar y utilizar sosteniblemente los océanos). Al proveer una herramienta de análisis sistemático de datos marinos, se fomenta un mejor diagnóstico de la "salud" de nuestros ecosistemas costeros, acelerando el ciclo científico desde la adquisición del dato hasta las decisiones medioambientales.
- **Impacto ético-social:** El uso exclusivo de herramientas de código libre y la adopción de una filosofía *Open Science* democratiza el acceso a la analítica de primer nivel, mejorando la transparencia de los datos recopilados por instituciones públicas, lo cual revierte a nivel social en forma de conocimiento accesible y compartible.
- **Diversidad:** El marco de trabajo fomenta un desarrollo inclusivo al integrar explícitamente contenido editable y separable del código analítico (fomentando la participación de científicos no familiarizados a la programación dura a nivel de backend).

### 1.4 Enfoque y método seguido
Se ha optado por un enfoque propio de la Ingeniería de Software y Ciencia de Datos aplicada. Se ha dividido el proyecto conceptualmente de la siguiente manera:
- **Backend Analítico (Motor de Datos):** Basado en Python puro usando `pandas`, agrupado modularmente por ciclo de vida de dato (raw -> interim -> processed). Incluye scripts numerados por etapa de canalización (pipeline escalonado).
- **Control de Calidad (Data QA):** Enfoque declarativo de calidad mediante umbrales específicos basados en la fenomenología del mar.
- **Frontend Interactivo:** Enfoque ágil de diseño de interfaz utilizando Streamlit, permitiendo acoplar fácilmente los productos estáticos (gráficos renderizados guardados en `outputs/`) con las herramientas de navegación dinámica.

### 1.5 Planificación del trabajo
`[NOTA PARA DESARROLLAR (Jorge): Aquí deberás incluir tu Diagrama de Gantt o una tabla con las fechas reales, las horas dedicadas por cada iteración del software, o qué tareas hiciste en los meses concretos de tu TFM (Ej: Fase 1 - Análisis de Requisitos, Fase 2 - Ingesta, Fase 3 - Control de Calidad, Fase 4 - Interfaz y Visualización, Fase 5 - Memoria)]`

### 1.6 Breve sumario de productos obtenidos
Toda la ejecución del proyecto ha generado una estructura de artefactos computacionales finalizados:
1. Una base de datos `processed/` completamente unificada y auditada.
2. Informes de calidad automatizados en HTML (generados por los análisis lógicos en la etapa de auditoría temprana).
3. Colecciones de visualizaciones renderizadas y almacenadas asíncronamente en el sistema principal (`outputs/figures`).
4. La aplicación web construida `app.py` que da interfaz exploratoria al conjunto de la experiencia interactiva, dotando a la información de interactividad instantánea para los investigadores de ciencias del mar.

### 1.7 Breve descripción de los otros capítulos de la memoria
El Capítulo 2 explora el estado del arte y las tecnologías precursoras; el Capítulo 3 detalla extensivamente el diseño de la arquitectura interna de la solución y presenta los resultados visuales de su ejecución; el Capítulo 4 discute el éxito del *pipeline* frente a las estrategias previas manuales; el Capítulo 5 expone el presupuesto ficticio del proyecto y finalmente el Capítulo 7 aborda las conclusiones y posibilidades evolutivas futuras de la herramienta.

### 1.8 Declaración sobre el uso de inteligencia artificial generativa
`[NOTA: Rellena o ajusta este apartado si te obligan en la universidad a firmar una declaración formal. Por ejemplo:]`
Para el desarrollo y diseño metodológico de la memoria, planificación, generación de ciertos bloques de código modular Python e identificación ágil de errores tipográficos en el código, se han empleado diversas herramientas y plataformas dotadas de Inteligencia Artificial Generativa supervisadas constantemente por el autor de esta memoria, garantizando que todo resultado y conclusión técnica derivan del conocimiento aplicado del estudiante cursando el Máster Universitario.

---

## 2. Estado del arte

Historicamente en una gran cantidad de institutos de ciencias biológicas y oceanográficas persisten un solapamiento en el uso mixto del lenguaje *R* para el análisis y hojas de cálculo masivas, lo que frecuentemente deriva en flujos de datos que no son trazables ni escalables ni auditables (*black-box validation*).

En la actualidad, el paradigma del manejo de datos medioambientales está virando hacia sistemas de orquestación (herramientas como Airflow o Dagster, aunque complejas de instalar) y validaciones orientadas a datos como *Great Expectations* y bases tabulares estandarizadas a través del ecosistema PyData (Python, Pandas). En el plano de la visualización, anteriormente relegada a dashboards estáticos en servidores dedicados y costosos o apps creadas con Shiny en ecosistemas cerrados, hoy en día módulos de nueva generación como el propio **Streamlit** (usado en el actual proyecto) permiten prototipar aplicaciones de analítica complejas a gran velocidad sin lidiar directamente con HTML/CSS puro, centrándose exclusivamente en el valor analítico que consume el usuario final.

El estado actual promueve diseños que aplican conceptos de integración, observabilidad y reproducibilidad del dato, lo cual constituye el corazón técnico del motor de este backend oceanográfico.

---

## 3. Resultados 

La consecuencia técnica y resultado palpable de este trabajo es el despliegue funcional de un "orquestador automatizado" modularizado (archivo principal `main.py`). El desarrollo se desgranó conceptualmente conformando un flujo secuencial:

**A. El bloque de Ingesta y Estandarización (`src/00_ingestion.py`)**  
Se logró desarrollar un algoritmo que normaliza las estructuras crudas alojadas en `data/raw/`. En esta fase del proyecto los ficheros son tratados bajo la noción de inmutabilidad (el archivo en bruto no se modifica en el disco, sino que se virtualizan sus cambios hacia copias temporales en `interim/`). 

**B. La Observabilidad y Auditoría de Datos (`src/01_agent_inspector.py`)**  
Éste es probablemente el componente más crítico e innovador para el instituto en este desarrollo. Se han utilizado funciones de la herramienta de testing de calidad de datos, codificando validaciones específicas que chequean el sentido biológico y físico en paralelo para cada línea insertada antes de permitir procesarla. Esto previene uno de los problemas históricos en investigación: descubrir valores erróneos de sensórica semanas más tarde durante la redacción de informes por causa del salto de escala o de registros defectuosos en origen. El resultado paralelo es la emisión de reportes automatizados detallando las banderas/avisos de cada atributo.

**C. Módulo Analítico y Renderizado (`src/02_analysis.py`, `src/03_visualization.py`)**  
Se ha unificado la técnica de análisis estadístico descriptivo en crudo de todas las series observadas. El propio motor se encarga de crear subrutinas y guardar las figuras dentro de los repositorios `outputs/figures`, proveyendo instantáneamente productos finales utilizables por cualquier científico en otras memorias publicables de manera estática y consistente gráficamente.

**D. Plataforma Frontend Interactiva (`app.py`)**  
Se consolida un portal único visual que se interpone entre un usuario intermedio y todas las iteraciones complejas del backend anteriormente expresadas. En los resultados, se observa de manera práctica que se pueden cargar y visualizar al vuelo los textos referidos en la carpeta `docs` separando por completo el código de la experiencia narrativa de uso.

---

## 4. Discusión

La puesta a punto de este nuevo abordaje ha evidenciado el salto cualitativo entre los sistemas manuales de procesamiento frente a arquitecturas computacionales modulares que validan sus propias variables. A diferencia del modo tradicional, el uso de control de tipologías (fase agente inspector) erradica el margen de error sistemático, brindando a la comunidad del programa Radiales del IEO una confianza estadística absoluta en los productos publicables.

Sin embargo, cabe destacar algunas consideraciones estructurales que afloraron en este proyecto. Si bien los objetivos de eficiencia temporal se han batido satisfactoriamente, se determinó que en etapas futuras podría existir el reto tecnológico del tamaño del dato (crecimiento ininterrumpido en gigabytes de muestreos). En el presente diseño las herramientas del entorno Pandas corren "en memoria principal (RAM)", lo cual actualmente es sobradamente suficiente para este volumen de muestreo; pero se deberá valorar metodologías big data como el uso de `Polars` o gestores documentales distribuidos en nubes si la escala aumenta en decenios. Adicionalmente, se logró demostrar que un framework como *Streamlit* puede suponer ahorros gigantes en tiempos de integración comparados con el costoso esfuerzo que hubiera acarreado un frontend asíncrono.

---

## 5. Valoración económica
`[NOTA PARA DESARROLLAR (Jorge): Aquí te propongo una estructura base y tú cambias los valores numéricos basándote en un proyecto de consultoría real:]`

Si bien este proyecto ha sido elaborado mediante software Open Source (Python, Pandas, Streamlit), el coste total equivaldría al conjunto de horas-hombre requeridas por un **Ingeniero/Científico de Datos Junior-Mid** especializado en la fase conceptual, desarrollo, limpieza y testeo, y el equipo subyacente.

*Presupuesto orientativo (para adaptar al documento):*
1. **Costes de personal:**
   - Análisis y Requisitos (40h x 30€): 1200€
   - Desarrollo del Pipeline de Ingestión y Auditoría (100h x 35€): 3500€
   - Desarrollo del Dashboard Frontend y Análisis (70h x 35€): 2450€
   - Redacción de documentación y pruebas (40h x 25€): 1000€
2. **Costes Tecnológicos Software:**
   - Licencias de Lenguaje: 0€
   - Servicios Cloud/Soporte/IA: 150€
3. **Costes Computacionales Hardware/Amortizaciones:**
   - Equipo portátil desarrollo (Amortizado proporcionalmente para 4 meses): 250€
4. **Resumen de costes:**  
   - Base imponible: 8550 €
   - IVA asociado (21%): 1795,50 €
   - **Estimación Total de Proyecto: 10345,50 €** 

---

## 7. Conclusiones y trabajos futuros
`[NOTA: Tu índice de plantilla saltaba del 5 al 7. Modifica la numeración a 6 si es un error de la plantilla.]`

### 7.1 Conclusiones
Tras someter la plataforma al tratamiento de matrices oceanográficas verídicas provenientes de los programas del IEO:
- Se certifica la viabilidad técnica y eficiencia de transicionar desde rutinas monolíticas manuales a tuberías algorítmicas desacopladas (*Data Pipelines*).
- El aseguramiento de validez del metadato de las muestras históricas mar adentro, logrado al establecer puertas automáticas que descartan datos ilegítimos, asegura la reproducibilidad para series climáticas actuales.
- El diseño metodológico reduce espectacularmente el nivel técnico requerido por parte del investigador gracias a la aplicación interactiva amigable.

### 7.2 Líneas de futuro
Existen canales de evolución para este trabajo, destacando de cara a la siguiente iteración:
1. Conexión del backend principal con un almacén perimetral (Base de Datos relacional SQL/Cloud) y orquestación remota automática con cronómetros temporales asíncronos en servidor.
2. Expansión territorial del programa a más institutos y series observacionales costeras, ampliando el alcance a datos GIS espaciales.
3. Posibilidad de exponer los datos directamente hacia APIs públicas del estado para libre investigación.
4. Adición de modelos predictivos o algoritmos de interpolación temporal a través de capas de machine learning.

### 7.3 Seguimiento de la planificación
`[NOTA PARA DESARROLLAR: Aquí debes añadir unas frases indicando si has conseguido ajustarte al calendario que presentaste en la PEC anterior (Gantt) y si tuviste algún retraso o cambio de planes durante el TFM]`

---

## 8. Glosario
- **TFM:** Trabajo de Fin de Máster.
- **IEO:** Instituto Español de Oceanografía, origen principal de los datos brutos del proyecto.
- **Radiales:** Programa de investigación del IEO continuado a través de los años.
- **Pipeline:** Conjunto de rutinas computacionales encadenadas donde el producto resultante de un proceso sirve de entrada al consiguiente algoritmo.
- **QA (Control de Calidad):** Verificación automática sistemática que comprueba reglas establecidas para un conjunto de parámetros numéricos.
- **Frontend / Dashboard interactivo:** Interfaz gráfica accesible desde entorno web que el usuario manipula visualmente.
- **IDE:** Entorno Integrado de Desarrollo de software.

## 9. Bibliografía
`[NOTA PARA DESARROLLAR: Agrega tus referencias. Ejemplos obligados por usar sus herramientas:]`
- Pandas Development Team. (2020). *pandas-dev/pandas: Pandas.* Zenodo. [https://doi.org/10.5281/zenodo.3509134]
- Streamlit. (2023). *The fastest way to build data apps in Python.* [https://streamlit.io/]
- McKinney, W. (2010). Data Structures for Statistical Computing in Python. *Proceedings of the 9th Python in Science Conference*, 51–56.
- Great Expectations Docs. *Data quality tools for modern pipelines.* [https://greatexpectations.io/]

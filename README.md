# IEO Orchestrator — Pipeline y Visualización de Series Temporales Oceanográficas

> **Trabajo de Fin de Máster** | Pipeline de datos y plataforma web interactiva para el análisis de radiales oceanográficos del IEO (Instituto Español de Oceanografía).

---

## ¿Qué hace este proyecto?

Diseña e implementa un **pipeline integral de datos** (ingesta, validación de calidad, análisis estadístico) y una **plataforma web interactiva** (Streamlit) para explorar series temporales históricas de muestreos marinos.

La arquitectura prioriza **automatización**, **reproducibilidad**, **control de calidad riguroso del dato** y su accesibilidad a través de visualizaciones interactivas.

---

## 🏗️ Estructura del Proyecto

```text
IEO-Orchestrator/
├── data/                      ← Ciclo de vida de los datos (ver nota ↓)
│   ├── raw/                   Datos brutos originales (punto de partida)
│   ├── interim/               Archivos temporales generados al unificar formatos
│   ├── processed/             Datos finales limpios y validados
│   ├── quarantine/            Registros marcados por el inspector ML
│   └── pending_review/        Datos pendientes de revisión manual
├── src/                       ← Lógica de backend y análisis
│   ├── agents/
│   │   ├── agent_curator.py   Curador de datos vía IA
│   │   └── agent_inspector.py Inspector de calidad vía IA
│   ├── 00_data_scout.py       Reconocimiento y reporte de datos en raw/
│   ├── 00_ingestion.py        Estandarización y limpieza estructural
│   ├── 01_agent_inspector.py  Auditoría de calidad (Great Expectations)
│   ├── 02_analysis.py         Cálculos, estadística y modelado
│   ├── 03_visualization.py    Generación de gráficos estáticos
│   ├── visualization.py       Fachada de importación para app.py
│   └── fig_export.py          Exportación de figuras a PNG
├── outputs/                   ← Productos generados por los scripts
│   ├── figures/               Gráficos generados (PNG)
│   └── reports/               Informes de validación de calidad
├── docs/                      ← Documentación y contenido editorial
│   ├── metodologia_*.md       Textos metodológicos (cargados por la web)
│   ├── data_dictionary.yaml   Diccionario de variables procesadas
│   └── descripcion_Radiales.txt
├── assets/
│   └── logo                   Logo de la interfaz web
├── app.py                     Frontend (Streamlit) — plataforma web interactiva
├── main.py                    Orquestador — ejecuta el pipeline completo
├── lanzador.bat               Script de arranque rápido para Windows
├── requirements.txt           Dependencias Python
└── README.md
```

> [!IMPORTANT]
> **Las carpetas `data/` y `outputs/` están vacías** (solo contienen un `.gitkeep`).
> Para iniciar el pipeline, coloca el archivo de datos brutos (`ExcelSirenoGijon.xls` o equivalente) en `data/raw/` y ejecuta `python main.py`.

---

## ⚙️ Flujo de Trabajo

```
data/raw/  →  00_data_scout.py  →  00_ingestion.py  →  01_agent_inspector.py
                                                              ↓
                                         data/processed/  +  data/quarantine/
                                                              ↓
                                                         app.py (Streamlit)
```

1. **Reconocimiento** (`00_data_scout.py`): genera un reporte de la estructura del raw antes de procesar nada.
2. **Ingesta** (`00_ingestion.py`): estandariza formatos irregulares y produce un CSV tabular limpio.
3. **Inspección** (`01_agent_inspector.py`): audita la calidad física/biológica del dato; los registros anómalos van a `quarantine/`.
4. **Análisis y visualización** (`02_analysis.py`, `03_visualization.py`): estadísticas, tendencias y gráficos a disco.
5. **Plataforma web** (`app.py`): interfaz Streamlit para exploración interactiva de los datos validados.

---

## 🚀 Instalación y Arranque

### 1. Entorno Python

```bash
# Python 3.11 o 3.12 recomendado
pip install -r requirements.txt
```

### 2. Datos

Coloca el archivo de datos en `data/raw/` (el pipeline espera `ExcelSirenoGijon.xls` para Radiales Gijón).
> ⚠️ Los datos reales del IEO **no se incluyen** en este repositorio.

### 3. Ejecutar el pipeline

```bash
python main.py
```

### 4. Lanzar la plataforma web

```bash
streamlit run app.py
```

En Windows puedes usar `lanzador.bat` para arrancar directamente.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
|---|---|
| Orquestación e ingesta | Python, Pandas, Pathlib |
| Calidad de datos | Great Expectations |
| Visualización estática | Plotly, Seaborn, Matplotlib |
| Plataforma web | Streamlit |

---

## 📁 Notas

- Los textos metodológicos se editan en `docs/metodologia_*.md` y la web los carga automáticamente.
- `src/archive/` contiene módulos en desarrollo no activos en el pipeline principal. No se incluye en el repositorio.
- La carpeta `auditoria_advicExplorer/` (análisis de la aplicación R Shiny adviceXplorer del ICES) se mantiene localmente y no forma parte de este repositorio.

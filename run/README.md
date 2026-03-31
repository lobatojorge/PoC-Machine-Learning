## Carpeta `run/` — Ejecución del proyecto

Esta carpeta agrupa **todos los artefactos necesarios para ejecutar** el repositorio sin ruido en la raíz.

- `app.py`: entrada de la aplicación **Streamlit** (visor interactivo).
- `main.py`: **orquestador** del pipeline (ingesta → inspección → análisis).
- `lanzador.bat`: script de conveniencia para Windows que:
  - crea/activa un entorno virtual `venv/`,
  - instala `requirements.txt`,
  - lanza `streamlit run app.py`.
- `requirements.txt`: lista de dependencias Python del proyecto.
- `.gitignore`: reglas de exclusión aplicadas a esta carpeta (útil si se generan artefactos locales aquí).
- `assets/`: recursos estáticos necesarios para la UI (por ejemplo, `logo.webp` usado como icono de la app).

### Uso rápido

Desde la raíz del repo:

```bash
cd run
python -m venv venv         # si no existe
venv\Scripts\activate       # Windows
pip install -r requirements.txt
python main.py              # Ejecuta el pipeline completo
streamlit run app.py        # Lanza la interfaz web
```


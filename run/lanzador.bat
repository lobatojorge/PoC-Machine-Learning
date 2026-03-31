@echo off
cd /d "%~dp0"
echo ===================================================
echo   Iniciando Arquitectura de Datos Oce�nicos...
echo ===================================================

echo.
echo [1/3] Comprobando entorno virtual...
if not exist venv\Scripts\activate.bat (
    echo Creando entorno virtual nuevo...
    python -m venv venv
) else (
    echo Entorno virtual detectado.
)

echo.
echo [2/3] Activando entorno e instalando dependencias (requirements.txt)...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo [3/3] Levantando el panel de Streamlit...
streamlit run app.py

pause


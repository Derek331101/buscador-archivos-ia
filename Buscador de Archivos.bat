@echo off
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al iniciar la aplicacion. Revisa el mensaje de arriba.
    echo.
    pause >nul
)

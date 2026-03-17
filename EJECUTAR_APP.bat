@echo off
title Voice Cloner
cd /d "%~dp0"

echo Iniciando Voice Cloner...
echo.

python voice_cloner_app.py
if errorlevel 1 (
    echo.
    echo Error al ejecutar. Comprueba que Python este instalado.
    pause
)

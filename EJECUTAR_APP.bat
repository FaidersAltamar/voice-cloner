@echo off
cd /d "%~dp0"
python voice_cloner_app.py
if errorlevel 1 pause

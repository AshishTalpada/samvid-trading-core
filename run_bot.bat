@echo off
title Institutional Trading System V3.0
color 0A

echo [================================================]
echo   Trading System V3.0 - Automated Boot Sequence
echo [================================================]
echo.

:: 1. Start Docker Desktop for QuestDB (HFT)
echo [1/3] Checking Docker Engine for HFT Streamer...
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker is offline. Starting Docker Desktop natively...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting 45 seconds for Docker Daemon to spool up...
    timeout /t 45 >nul
) else (
    echo Docker Engine is already running!
)

:: 2. Boot up QuestDB container
echo.
echo [2/3] Booting up QuestDB (High-Frequency Database)...
docker-compose -f docker-compose.questdb.yml up -d

:: 3. Launch System with the uv-managed virtual environment
echo.
echo [3/3] Binding Virtual Environment and Spawning Agents...
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    echo WARNING: Falling back to legacy virtual environment 'venv'.
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    echo ERROR: No project virtual environment was found.
    exit /b 1
)

:: Run the script
"%PYTHON_EXE%" src\main.py

echo.
pause

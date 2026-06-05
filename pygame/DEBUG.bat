@echo off
REM P28.9 — debug launcher. Same setup as PLAY.bat but uses python.exe
REM (with console) and `pause` at end so crashes / tracebacks stay
REM visible. Use this when the game won't start or you want to see
REM stdout / stderr from a playthrough.
title Dungeon Kraulem (DEBUG)
cd /d "%~dp0"

set PYGAME_HIDE_SUPPORT_PROMPT=1

python -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo pygame not found. Installing pygame-ce...
    pip install pygame-ce --prefer-binary
    if errorlevel 1 (
        pip install pygame --prefer-binary
    )
    python -c "import pygame" >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Could not install pygame. Ensure Python 3 + pip are in PATH.
        pause
        exit /b 1
    )
)

python main.py
echo.
echo --- gra zakonczona (kod wyjscia: %errorlevel%) ---
pause

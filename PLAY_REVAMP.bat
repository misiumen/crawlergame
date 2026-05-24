@echo off
title CRAWL PROTOCOL - Revamp
cd /d "%~dp0"

REM Ensure pygame is available (pygame-ce preferred on Windows)
python -c "import pygame" 2>nul
if errorlevel 1 (
    echo pygame not found. Attempting to install pygame-ce...
    pip install pygame-ce --prefer-binary
    if errorlevel 1 (
        pip install pygame --prefer-binary
    )
    python -c "import pygame" 2>nul
    if errorlevel 1 (
        echo Could not install pygame. Ensure Python 3 and pip are in PATH.
        pause
        exit /b 1
    )
)

python main_revamp.py
pause

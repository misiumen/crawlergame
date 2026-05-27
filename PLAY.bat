@echo off
title Dungeon Kraulem
cd /d "%~dp0"

REM P28.9 — hide the pygame-ce support banner so the install probe is silent.
REM Without this, "import pygame" prints its version + SDL info to stdout,
REM which was showing twice in the launcher console (probe + actual run).
set PYGAME_HIDE_SUPPORT_PROMPT=1

REM Probe pygame quietly. Only show output if something goes wrong.
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

REM P28.9 — launch via pythonw (no-console variant of Python) and DETACH
REM the .bat immediately. This closes the launcher console window the
REM moment the game window opens — no more orphaned "Press any key to
REM continue" prompt after every session.
REM
REM `start ""` keeps the .bat from blocking; the empty quoted title is
REM required by `start` when the first arg looks like a path.
start "" pythonw main.py

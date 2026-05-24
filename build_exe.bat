@echo off
REM Build standalone Windows .exe for the revamp build.
REM Output: dist/CrawlProtocol.exe  (single file, ~30-60 MB)
REM
REM Requirements (one-time): pip install pyinstaller pygame-ce
REM Run this file by double-clicking.

title Build CRAWL PROTOCOL .exe
cd /d "%~dp0"

REM Verify Python is in PATH
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found on PATH. Install Python 3.11+ and retry.
    pause
    exit /b 1
)

REM Ensure pyinstaller + pygame-ce are installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install --upgrade pyinstaller
)

python -c "import pygame" 2>nul
if errorlevel 1 (
    pip install pygame-ce --prefer-binary
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist CrawlProtocol.spec del /q CrawlProtocol.spec

echo.
echo === Building one-file .exe ===
echo.

REM --onefile      : single .exe
REM --noconsole    : no command-prompt window behind the game
REM --name         : output executable name
REM --add-data     : bundle locales and assets (note Windows separator ';')
REM --hidden-import: be explicit about packages PyInstaller might miss
python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name CrawlProtocol ^
    --add-data "revamp/locales;revamp/locales" ^
    --add-data "assets;assets" ^
    --collect-submodules revamp ^
    --collect-submodules revamp.data ^
    --hidden-import pygame ^
    main.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo === Build succeeded ===
echo Executable: %CD%\dist\CrawlProtocol.exe
echo Run it directly. No Python required on the target machine.
echo.
pause

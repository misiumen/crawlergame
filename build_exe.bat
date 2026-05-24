@echo off
REM Build standalone Windows .exe for Dungeon Kraulem.
REM Output: DungeonKraulem.exe in the game's main folder (next to this .bat).
REM A copy is also kept in dist/DungeonKraulem.exe for back-compat.
REM
REM Requirements (one-time): pip install pyinstaller pygame-ce
REM Run this file by double-clicking.

title Build Dungeon Kraulem .exe
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

REM Clean previous builds (including any old exe in the main folder so
REM the player never accidentally launches a stale build). Also remove
REM the legacy CrawlProtocol.exe / .spec from before the rename.
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist DungeonKraulem.spec del /q DungeonKraulem.spec
if exist DungeonKraulem.exe del /q DungeonKraulem.exe
if exist CrawlProtocol.spec del /q CrawlProtocol.spec
if exist CrawlProtocol.exe del /q CrawlProtocol.exe

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
    --name DungeonKraulem ^
    --add-data "dungeon_kraulem/ui/locales;dungeon_kraulem/ui/locales" ^
    --add-data "assets;assets" ^
    --collect-submodules dungeon_kraulem ^
    --collect-submodules dungeon_kraulem.content.data ^
    --hidden-import pygame ^
    main.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

REM Copy the freshly-built exe into the game's main folder so the player
REM never has to dig into dist\ to launch the newest build.
if exist dist\DungeonKraulem.exe (
    copy /Y dist\DungeonKraulem.exe DungeonKraulem.exe >nul
) else (
    echo WARNING: dist\DungeonKraulem.exe was not produced.
)

echo.
echo === Build succeeded ===
echo Executable: %CD%\DungeonKraulem.exe   (main folder)
echo Backup    : %CD%\dist\DungeonKraulem.exe
echo Run it directly. No Python required on the target machine.
echo.
pause

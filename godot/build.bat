@echo off
REM Rebuild the playable Windows exe. Double-click or run from a terminal.
setlocal
set GODOT="C:\Users\micha\Downloads\Godot_v4.6.3-stable_win64_console.exe"
set PROJ=%~dp0
echo Importing...
%GODOT% --headless --import --path "%PROJ%" >nul 2>&1
echo Exporting...
%GODOT% --headless --path "%PROJ%" --export-release "Windows Desktop" "%PROJ%builds\DungeonKraulem.exe"
echo.
echo Built: %PROJ%builds\DungeonKraulem.exe
endlocal

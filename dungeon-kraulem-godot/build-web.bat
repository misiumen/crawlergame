@echo off
REM Build the HTML5 / Web version into builds\web\.
REM PREREQUISITE: install the matching "Web" export templates once via the Godot
REM editor (Editor > Manage Export Templates > Download), or this will error with
REM "No export template found". Then double-click this file.
setlocal
set GODOT="C:\Users\micha\Downloads\Godot_v4.6.3-stable_win64_console.exe"
set PROJ=%~dp0
set PROJ=%PROJ:~0,-1%
if not exist "%PROJ%\builds\web" mkdir "%PROJ%\builds\web"
echo Importing...
%GODOT% --headless --import --path "%PROJ%" >nul 2>&1
echo Exporting Web...
%GODOT% --headless --path "%PROJ%" --export-release "Web" "%PROJ%\builds\web\index.html"
echo.
echo Built: %PROJ%\builds\web\index.html
echo Zipping for itch.io...
powershell -NoProfile -Command "Compress-Archive -Force -Path '%PROJ%uilds\web\*' -DestinationPath '%PROJ%uilds\dungeon-kraulem-web.zip'"
echo Built: %PROJ%uilds\dungeon-kraulem-web.zip  (upload this to itch.io as an HTML game)
echo Serve it over HTTP (browsers block file://) e.g.:  python -m http.server -d builds\web
endlocal

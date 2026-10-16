@echo off
setlocal
REM Lance le crew dashboard en standalone (double-clic, hors session Claude).
REM Venv isole a la racine du projet (%ROOT%\.dashboard-venv, gitignore), jamais
REM l'environnement Python du projet. cwd = racine du repo (le serveur lit/ecrit
REM ./crew/).
REM
REM Localisation de server.py, par ordre de priorite :
REM   1. %CREW_DASHBOARD_DIR%  (dossier contenant server.py, override manuel)
REM   2. %ROOT%\scripts\dashboard  (clone de claude-crew lui-meme)
REM   3. plugin installe : %USERPROFILE%\.claude\plugins\cache\claude-crew\
REM      claude-crew\<version>\scripts\dashboard  (version la plus haute contenant server.py)
REM CLAUDE_PLUGIN_ROOT n'existe que dans une session Claude, d'ou ce scan.

set "ROOT=%~dp0.."
set "VENV=%ROOT%\.dashboard-venv"
set "SRV="

if defined CREW_DASHBOARD_DIR if exist "%CREW_DASHBOARD_DIR%\server.py" set "SRV=%CREW_DASHBOARD_DIR%"
if not defined SRV if exist "%ROOT%\scripts\dashboard\server.py" set "SRV=%ROOT%\scripts\dashboard"
if not defined SRV (
    for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$c = Join-Path $env:USERPROFILE '.claude\plugins\cache\claude-crew\claude-crew'; if (Test-Path -LiteralPath $c) { Get-ChildItem -LiteralPath $c -Directory | Where-Object { $_.Name -match '^\d+(\.\d+)+$' } | Sort-Object { [version]$_.Name } -Descending | ForEach-Object { Join-Path $_.FullName 'scripts\dashboard' } | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'server.py') } | Select-Object -First 1 }"`) do set "SRV=%%D"
)
if not defined SRV (
    echo [dashboard.bat] server.py introuvable. Installe le plugin claude-crew
    echo   ^(/plugin install claude-crew@claude-crew^) ou definis CREW_DASHBOARD_DIR.
    call :fail
    exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -m venv "%VENV%"
    ) else (
        python -m venv "%VENV%"
    )
)

"%VENV%\Scripts\python.exe" -m pip install -q -r "%SRV%\requirements.txt"
if errorlevel 1 (
    echo [dashboard.bat] echec de l'installation des dependances.
    call :fail
    exit /b 1
)

pushd "%ROOT%"
"%VENV%\Scripts\python.exe" "%SRV%\server.py"
popd
exit /b 0

:fail
REM Double-clic : garder la fenetre ouverte pour lire l'erreur.
echo %cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "/c" >nul && pause
exit /b 0

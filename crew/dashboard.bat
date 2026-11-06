@echo off
setlocal
REM Launches the crew dashboard standalone (double-click, outside a Claude session).
REM Isolated venv at the project root (%ROOT%\.dashboard-venv, gitignored), never
REM the project's own Python environment. cwd = repo root (the server reads/writes
REM ./crew/).
REM
REM Where server.py is looked up, in priority order:
REM   1. %CREW_DASHBOARD_DIR%  (folder containing server.py, manual override)
REM   2. %ROOT%\scripts\dashboard  (clone of crew-mates itself)
REM   3. installed plugin: %USERPROFILE%\.claude\plugins\cache\crew-mates\
REM      crew-mates\<version>\scripts\dashboard  (highest version containing server.py)
REM CLAUDE_PLUGIN_ROOT only exists inside a Claude session, hence this scan.

set "ROOT=%~dp0.."
set "VENV=%ROOT%\.dashboard-venv"
set "SRV="

if defined CREW_DASHBOARD_DIR if exist "%CREW_DASHBOARD_DIR%\server.py" set "SRV=%CREW_DASHBOARD_DIR%"
if not defined SRV if exist "%ROOT%\scripts\dashboard\server.py" set "SRV=%ROOT%\scripts\dashboard"
if not defined SRV (
    for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$c = Join-Path $env:USERPROFILE '.claude\plugins\cache\crew-mates\crew-mates'; if (Test-Path -LiteralPath $c) { Get-ChildItem -LiteralPath $c -Directory | Where-Object { $_.Name -match '^\d+(\.\d+)+$' } | Sort-Object { [version]$_.Name } -Descending | ForEach-Object { Join-Path $_.FullName 'scripts\dashboard' } | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'server.py') } | Select-Object -First 1 }"`) do set "SRV=%%D"
)
if not defined SRV (
    echo [dashboard.bat] server.py not found. Install the crew-mates plugin
    echo   ^(/plugin install crew-mates@crew-mates^) or set CREW_DASHBOARD_DIR.
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
    echo [dashboard.bat] dependency installation failed.
    call :fail
    exit /b 1
)

pushd "%ROOT%"
"%VENV%\Scripts\python.exe" "%SRV%\server.py"
popd
exit /b 0

:fail
REM Double-click: keep the window open so the error can be read.
echo %cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "/c" >nul && pause
exit /b 0

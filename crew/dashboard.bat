@echo off
REM Lance le crew dashboard (scripts/dashboard/server.py) pour ce projet, en
REM standalone (double-clic, hors session Claude) plutot que via le skill
REM /crew-dashboard. Venv isole (jamais l'environnement Python du projet
REM cible), cwd = racine du repo pour que le serveur lise/ecrive ./crew/.
REM
REM Venv place a la racine du projet (%ROOT%\.dashboard-venv), PAS au meme
REM endroit que le skill (${CLAUDE_PLUGIN_ROOT}/.dashboard-venv, un seul venv
REM partage entre tous les projets) : CLAUDE_PLUGIN_ROOT n'existe que dans
REM l'environnement d'une session Claude, jamais pour un .bat lance a la
REM main hors Claude Code. Deux venvs distincts, deux contextes de lancement
REM distincts, pas une incoherence. Voir .claude/skills/crew-dashboard/SKILL.md
REM et docs/superpowers/specs/2026-09-02-crew-dashboard-design.md § Delivery.

set "ROOT=%~dp0.."
set "VENV=%ROOT%\.dashboard-venv"

if not exist "%VENV%\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -m venv "%VENV%"
    ) else (
        python -m venv "%VENV%"
    )
)

"%VENV%\Scripts\python.exe" -m pip install -q -r "%ROOT%\scripts\dashboard\requirements.txt"
if errorlevel 1 (
    echo [dashboard.bat] echec de l'installation des dependances.
    exit /b 1
)

pushd "%ROOT%"
"%VENV%\Scripts\python.exe" "%ROOT%\scripts\dashboard\server.py"
popd

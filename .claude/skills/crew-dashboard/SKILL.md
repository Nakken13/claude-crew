---
name: crew-dashboard
description: Lance un dashboard web local temps réel (tasks TODO/CURRENT_TASKS/PAUSED/ICEBOX, batches CLAUDE_BATCH.md, sessions concurrentes crew_lock.json) avec actions de gestion (déplacer une tâche, cocher un test, purger un lock). Trigger — "/crew-dashboard", "interface crew", "dashboard des tâches", "visualiser l'état crew en temps réel".
---

Lance `scripts/dashboard/server.py` (FastAPI, `127.0.0.1` uniquement) dans
un venv **isolé du projet cible**, jamais dans son propre environnement
Python — un projet qui dépend déjà de FastAPI/uvicorn (n'importe quelle
version) ou n'a aucun environnement Python (ex. Next.js) n'est jamais
affecté. cwd = racine du projet courant : le serveur lit/écrit `./crew/`.

## Étapes

1. **Bootstrap venv** (une fois, réutilisé ensuite) :
   ```bash
   PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python)
   VENV="${CLAUDE_PLUGIN_ROOT}/.dashboard-venv"
   if [ ! -d "$VENV" ]; then
     "$PY" -m venv "$VENV"
   fi
   if [ -x "$VENV/bin/python" ]; then VPY="$VENV/bin/python"; else VPY="$VENV/Scripts/python.exe"; fi
   "$VPY" -m pip install -q -r "${CLAUDE_PLUGIN_ROOT}/scripts/dashboard/requirements.txt"
   ```
2. **Lancer le serveur en arrière-plan** (bloquant sinon — ne jamais
   l'exécuter en foreground) :
   ```bash
   "$VPY" "${CLAUDE_PLUGIN_ROOT}/scripts/dashboard/server.py"
   ```
   Le port réel (8943 par défaut, fallback OS-assigné si pris) est
   imprimé sur la première ligne de sortie — la lire avant de répondre à
   l'utilisateur, ne jamais supposer l'URL.
3. Communiquer l'URL à l'utilisateur (`http://127.0.0.1:<port>`).

## Lancement alternatif standalone

`crew/dashboard.bat` (Windows, double-clic, hors session Claude) fait le
même travail mais avec son propre venv à la racine du projet
(`<projet>/.dashboard-venv`, gitignoré) plutôt que le venv partagé
`${CLAUDE_PLUGIN_ROOT}/.dashboard-venv` ci-dessus — `CLAUDE_PLUGIN_ROOT`
n'existe pas hors d'une session Claude, donc les deux chemins sont
délibérément distincts, pas une incohérence à corriger.

## Tests (dev uniquement, pas partie du bootstrap ci-dessus)

`scripts/dashboard/test_server.py` (pytest) n'est pas couvert par
`requirements.txt` (fastapi/uvicorn seulement, ce que le venv bootstrap
installe). Pour lancer la suite, installer en plus
`scripts/dashboard/requirements-dev.txt` (pytest + httpx) dans le venv
utilisé, par ex. `"$VPY" -m pip install -q -r
"${CLAUDE_PLUGIN_ROOT}/scripts/dashboard/requirements-dev.txt"` puis
`"$VPY" -m pytest scripts/dashboard/test_server.py`.

## Ce que ce skill ne fait pas

- N'installe rien dans l'environnement du projet cible (§ isolation
  ci-dessus).
- Ne remplace pas les invariants du hook Stop/PreToolUse
  (`scripts/crew_hook.py`) : le serveur importe directement sa logique de
  collision/lock plutôt que de la dupliquer (voir
  `docs/superpowers/specs/2026-09-02-crew-dashboard-design.md`).
- Ne pousse jamais de commit : `POST /api/tasks/{slug}/move` fait un
  `git mv` local, comme le ferait `manager`, rien de plus.
- N'expose pas de panneau UI pour `POST /api/tests/{file}/toggle` en v1
  (3 panneaux seulement : Tasks/Batches/Sessions) — l'endpoint existe et
  est testé, mais pour l'instant seulement appelable en HTTP direct, pas
  cliquable depuis le dashboard.

---
name: crew-dashboard
description: Launches a local real-time web dashboard (tasks, batches, concurrent sessions) with management actions. Also triggers on — "/crew-dashboard", "interface crew", "dashboard des tâches", "task dashboard".
---

Runs `scripts/dashboard/server.py` (FastAPI, `127.0.0.1` only) in a venv
**isolated from the target project**, never in its own Python environment — a
project that already depends on FastAPI/uvicorn (any version) or has no Python
environment at all (e.g. Next.js) is never affected. cwd = root of the current
project: the server reads/writes `./crew/`.

## Steps

1. **Bootstrap the venv** (once, reused afterwards):
   ```bash
   PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python)
   VENV="${CLAUDE_PLUGIN_ROOT}/.dashboard-venv"
   if [ ! -d "$VENV" ]; then
     "$PY" -m venv "$VENV"
   fi
   if [ -x "$VENV/bin/python" ]; then VPY="$VENV/bin/python"; else VPY="$VENV/Scripts/python.exe"; fi
   "$VPY" -m pip install -q -r "${CLAUDE_PLUGIN_ROOT}/scripts/dashboard/requirements.txt"
   ```
2. **Launch the server in the background** (it blocks otherwise — never run it in
   the foreground):
   ```bash
   "$VPY" "${CLAUDE_PLUGIN_ROOT}/scripts/dashboard/server.py"
   ```
   The actual port (8943 by default, OS-assigned fallback if taken) is printed on
   the first line of output — read it before answering the user, never assume the
   URL.
3. Give the URL to the user (`http://127.0.0.1:<port>`).

## Alternative standalone launch

`crew/dashboard.bat` (Windows, double-click, outside a Claude session) does the
same job but with its own venv at the project root (`<project>/.dashboard-venv`,
gitignored) rather than the shared `${CLAUDE_PLUGIN_ROOT}/.dashboard-venv` above
— `CLAUDE_PLUGIN_ROOT` does not exist outside a Claude session, so the two paths
are deliberately distinct, not an inconsistency to fix.
The `.bat` is copied by `/crew-init` (`crew/` folder) and finds `server.py` in
the installed plugin (`%CREW_DASHBOARD_DIR%` > `scripts/dashboard/` > plugin
cache).

## Tests (dev only, not part of the bootstrap above)

`scripts/dashboard/test_server.py` (pytest) is not covered by `requirements.txt`
(fastapi/uvicorn only, what the bootstrap venv installs). To run the suite,
additionally install `scripts/dashboard/requirements-dev.txt` (pytest + httpx) in
the venv in use, e.g. `"$VPY" -m pip install -q -r
"${CLAUDE_PLUGIN_ROOT}/scripts/dashboard/requirements-dev.txt"` then
`"$VPY" -m pytest scripts/dashboard/test_server.py`.

## What this skill does not do

- Installs nothing in the target project's environment (§ isolation above).
- Does not replace the invariants of the Stop/PreToolUse hook
  (`scripts/crew_hook.py`): the server imports its collision/lock logic directly
  rather than duplicating it (see
  `docs/superpowers/specs/2026-09-02-crew-dashboard-design.md`).
- Never pushes a commit: `POST /api/tasks/{slug}/move` does a local `git mv`, as
  `manager` would, nothing more.
- Does not expose a UI panel for `POST /api/tests/{file}/toggle` in v1 (3 panels
  only: Tasks/Batches/Sessions) — the endpoint exists and is tested, but for now
  is only callable via direct HTTP, not clickable from the dashboard.

# Crew Dashboard — Design Spec

**Date:** 2026-09-02
**Status:** Approved

## Problem

Crew state (tasks, batches, sessions) lives entirely in markdown files and
`crew_lock.json`, readable only by grepping/opening files or running
`/crew-status` / `/crew-count`. There is no live, at-a-glance view, and no
way to act on that state (move a task, purge a stale lock) without going
through Claude in a session.

## Goal

A local, real-time web dashboard, shipped as part of the claude-crew
**scaffold** (usable by any project bootstrapped from the template — not
specific to this repo), that visualizes and manages:
- Tasks (TODO / CURRENT_TASKS / PAUSED / ICEBOX)
- Batches (`CLAUDE_BATCH.md`: zones, active/inactive, collisions)
- Concurrent sessions (`crew/CLAUDE_CONTEXT/crew_lock.json`: session_id →
  batch/tasks/worktree/branch/since, staleness vs TTL)

## Non-goals

- No auth / multi-user support (single local user, `127.0.0.1` only).
- No replacement for the crew hooks' own invariant enforcement — the
  dashboard reuses that logic, it does not reimplement or bypass it.
- No changes to `template/crew/` — the tool ships as a plugin script run
  against whatever project's `crew/` it's launched from, exactly like the
  existing hooks (`${CLAUDE_PLUGIN_ROOT}/scripts/...`), so nothing needs to
  be copied per-project.

## Architecture

`scripts/dashboard/server.py` — a FastAPI app, launched by a new skill
`crew-dashboard` (`/crew-dashboard`). Runs from the project root (cwd),
reads that project's `crew/`. Binds `127.0.0.1` only.

**Dependency isolation:** the dashboard's Python deps (fastapi, uvicorn)
are never installed into the target project's own environment. The skill
creates/reuses a dedicated venv at `${CLAUDE_PLUGIN_ROOT}/.dashboard-venv`
(stdlib `venv` module, first run only, no extra prereq beyond Python) and
launches `server.py` with that interpreter. A project that already depends
on FastAPI/uvicorn (any version) never collides with the dashboard's copy;
a Next.js-only project (no Python env) is unaffected — no pip install in
the project itself.

**Port selection:** default to a distinctive fixed port (8943, not
3000/8000 which collide with common Next.js/uvicorn dev servers); if
taken, fall back to an OS-assigned free port. The actual URL is always
printed on startup — never assumed.

**Logic reuse:** the server imports directly from `scripts/crew_hook.py`
— `check_batch_collisions`, lock load/purge/TTL helpers, task/batch
parsing — instead of reimplementing. This guarantees the dashboard can
never create a race the Stop-hook wouldn't otherwise catch, and any future
change to the invariants (lock schema, collision rule) only has one place
to change.

**Frontend:** static `index.html` + `app.js` + CSS served by FastAPI, no
build step, no Node dependency. Polls `GET /api/state` every 2-3s and
diff-renders (no full-page flicker). Chosen over SSE/file-watching: crew
state changes are low-frequency (task moves, checklist ticks), so polling
latency is invisible and the implementation stays dependency-free
(no `watchdog`).

## API

- `GET /api/state` — aggregates:
  - tasks per folder (TODO/CURRENT_TASKS/PAUSED/ICEBOX), parsed from
    filenames + frontmatter/content
  - batches from `CLAUDE_BATCH.md`: zone, task list, active vs "à classer"
  - sessions from `crew_lock.json`: session_id → batch/tasks/worktree/
    branch/since, with a stale flag when `since` exceeds the hook's
    `LOCK_TTL`
- `POST /api/tasks/{slug}/move` `{to}` — `git mv` between folders, gated
  by `check_batch_collisions` (same check `manager` runs before starting
  a task). Returns 409 with the conflicting batch/zone on collision.
- `POST /api/tests/{file}/toggle` `{item_index}` — flips one `- [ ]` /
  `- [x]` line in a `TESTS/IA/*.md` or `TESTS/DEV/*.md` file.
- `POST /api/sessions/{id}/purge` — force-removes a lock entry beyond
  TTL, reusing the hook's purge helper (manual override for a session
  that crashed before its own cleanup ran).

All mutating endpoints validate the `slug`/`file`/`id` path parameter
against files that actually exist under `crew/` — no path traversal, no
writes outside the crew tree.

## Frontend layout

Three panels only in v1 — `POST /api/tests/{file}/toggle` above is
implemented and tested, but has no dedicated panel yet; it's HTTP-only
until a Tests panel is worth adding.

- **Tasks** — one column per folder, a move action per task.
- **Batches** — zone, active/inactive, any collision warning.
- **Sessions** — table: id / batch / tasks / worktree / branch / since /
  stale badge / purge button.

## Testing

- `pytest` against fixture `crew/` trees (mirrors the existing
  `test_crew_hook.py` pattern): state-parsing correctness, collision-reuse
  behavior, move/purge correctness, path-traversal rejection.
- Live UI check via `claude-in-chrome` (this project's frontend-change
  rule) before the task is closed: golden path (view state, move a task,
  purge a lock) and edge cases (collision blocked, stale session shown).

## Delivery

- `scripts/dashboard/server.py` + `scripts/dashboard/static/` (new).
- `skills/crew-dashboard/SKILL.md` (new, + packaged copy
  `.claude/skills/crew-dashboard/SKILL.md`) — documents `/crew-dashboard`,
  handles first-run venv bootstrap.
- `crew/dashboard.bat` (new) — standalone Windows launcher (double-click,
  outside a Claude session), its own per-project venv since
  `CLAUDE_PLUGIN_ROOT` isn't available outside one. Not in the original
  plan; added because a human wants to open the dashboard without going
  through Claude Code first.
- Root `CLAUDE.md` skill-routing section gets one line pointing to it.
- `template/crew/` is untouched (Non-goals) — the tool runs from the
  installed plugin against any project's `crew/`, same as the existing
  hooks. `template/CLAUDE.md` itself *does* get the same one-line
  skill-routing addition as the root `CLAUDE.md`, so scaffolded projects
  discover `/crew-dashboard` too — narrower than "template/ untouched"
  read literally, but consistent with the Non-goal's actual scope.

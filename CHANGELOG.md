# Changelog

All notable changes to the `crew-mates` scaffold are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
version numbers match the `version` field in
[`.claude-plugin/plugin.json`](./.claude-plugin/plugin.json) (see
[`CONTRIBUTING.md`](./CONTRIBUTING.md) for the bump convention).

## [Unreleased]

- **Engine subprocesses no longer inherit std handles; mirrors are generated** — every `subprocess` call in the engine and the dashboard now pins stdin/stdout/stderr. On Windows a hook started with an invalid inherited handle made `git` die with `WinError 6`, so the closure auto-commit was skipped silently (it also made `test_auto_commit_closure_*` and the dashboard `test_move_*` tests fail intermittently). A static test enforces the invariant. New `scripts/dev/sync_engine.py` regenerates `scripts/`, `skills/` and `agents/` from their dogfood sources (`--check` for CI), and `verify_plugin_package.py` now also guards `scripts/crew_hook.py`, which was previously unchecked.
- **Remote claims for multi-dev repos (opt-in)** — `remote_claims : true` in the new `crew/CLAUDE_CONTEXT/CREW_CONFIG.md` (off by default, created by `/crew-update`, never overwritten) shares «who is on what» and the open `TODO` tasks through a dedicated git ref, `refs/crew/claims`, pushed on its own and never on `main`. New `crew_hook.py claims fetch|claim|release|publish|check-dup|materialize|list` (atomic compare-and-swap via `push --force-with-lease`, 8 h TTL, soft offline mode); `next-task` skips tasks and zones claimed by other devs, the session digest lists open remote tasks without network, the Stop hook warns when claims exist but the flag is off, and the dashboard gains a read-only team Kanban (`/api/claims`). `/crew-start`, `/crew-new-task` and `/crew-close-task` claim, publish (with duplicate check) and release. The dashboard is now responsive. Known limits are listed in `crew/CLAUDE_CONTEXT/AGENTS.md`.
- **`/crew-collab` — team mode switch** — solo by default (no remote branch, no claims, plain status bar). `/crew-collab on` asks for your name, turns on `remote_claims` and makes that name the owner of all your claims. Existing `TODO` tasks already owned by someone else are attributed without asking (an `Owner : <name>` line in the task, or a published claim); unmarked ones are set aside as "unassigned" without any question (`crew_hook.py ignore snapshot [--owner <name>]` names them): `/crew-start` never runs them, the status bar shows `👤N` (collab mode only; tasks added later stay startable). `/crew-collab status` lists who has how many tasks; `/crew-collab off` goes back to solo. New `crew_hook.py collab on|off|status` and `ignore snapshot|add|remove|list|off`.
- **`CLAUDE.md` slimmed ~10 KB → ~5 KB (≈4.5k → ≈2.2k tokens loaded every session).** Task lifecycle, batching/anti-collision, context-efficiency rules and detailed persona routing moved verbatim to the new on-demand engine file `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md` (added to `crew_update.py` engine files and to the template); `CLAUDE.md` keeps skill/persona routing, `/crew-*` commands and a few always-on rules. Hook messages, skills, agents and `CLAUDE_BATCH.md` point to the new doc instead of `CLAUDE.md § ...`.
- **Context-reset threshold unified at 150k tokens** for any window size (the Stop hook no longer uses 800k for 1M windows).

## [1.0.0] - 2026-10-30

- **BREAKING: plugin renamed `claude-crew` → `crew-mates`** (the `claude-` prefix is reserved for Anthropic's own plugins; `claude plugin validate` rejected it). The GitHub repo stays `Nakken13/claude-crew`. All `/crew-*` commands are unchanged; only the long prefix changes (`crew-mates:crew-start`). Migrate once per machine: `/plugin uninstall claude-crew`, `/plugin marketplace remove claude-crew`, `/plugin marketplace add Nakken13/claude-crew`, `/plugin install crew-mates@crew-mates`, then `/crew-update` in each project. `crew_update.py` still detects the old `claude-crew` entry in `enabledPlugins` for the double-hook check.
  - **Your projects are safe.** The `/plugin` commands only touch the plugin cache in `~/.claude/plugins`, never a project. `/crew-update` never writes `crew/TODO`, `CURRENT_TASKS`, `PROBLEMS`, `ICEBOX`, `PAUSED`, `TESTS`, `HISTORIQUE.md`, `TESTS_DONE` or `CLAUDE_BATCH.md`. It only updates engine files that are unchanged since its last write; a file you customized (`PRODUCT.md`, `CLAUDE.md`, `AGENTS.md`...) is reported as `conflict` and left alone.
  - **Recommended:** read the dry-run plan before confirming, keep your version for every `conflict`, and answer **no** if asked to "seed" the baseline on a project whose `PRODUCT.md`/`CLAUDE.md` you filled in by hand (that would mark your edits as untouched).
- **10 Zero-Token Claude Code Mods (`hooks/register.ts` + `hooks/mods/*.ts`)** — 100% local, zero-LLM-call, zero-dependency TypeScript mods declared via `"modules": ["./register.ts"]` in `hooks/hooks.json`:
  - **Visibility & Context (Mods 1–5):** `prompt-cache-control` (5m/1h TTL countdown, `cache_read` / `cache_creation` counters, `<60s` expiry alert), `token-weather` (1-line `☀️ Clear` → `⛅ Cloudy` → `⛈️ Storm` → `🚨 Compact soon` gauge), `turn-inspector` (`/crew-turns` side pane), `stack-viewer` (`/crew-stack` loaded session tree with source & priority), and `agent-flow` (`/crew-agents` live subagent execution tree).
  - **Tasks, Batches & Multi-Session (Mods 6–10):** `crew-radar` (`🟢 X Sessions en ligne | ⚡ Y Current Tasks | 📋 Z Todo` via `.claude/crew-sessions.lock` + `crew_lock.json`), `batch-progress` (live task checkbox `[████░░]` & global batch `[██████░░]` progress bars), `batch-dependency-graph` (`/crew-board` Kanban `Todo | In Progress | Done | Blocked` linked to active sessions), `file-lock-monitor` (instant UI collision alert on `Edit`/`Write`/`MultiEdit`), and `batch-eta-cost` (real-time remaining duration & tokens estimator from completed batch tasks).
  - **Unified `/crew-ui` command** — `/crew-ui [all|radar|progress|board|turns|stack|agents]` intercepted locally with zero token cost.
- **`seo` persona** — new « Référentiel Google » section (AEO/GEO = SEO, no `llms.txt`/chunking/AI schema for Google, Generative AI performance report, preferred sources, spam policies on AI responses, FAQ rich result deprecated, CWV thresholds) plus agent commerce (UCP spec 2026-08-25) and agent-ready sites (web.dev, 2026-04-01), each point sourced and dated; GEO and structured-data steps corrected accordingly.

## [0.5.1] - 2026-10-24

- Fix: `ROOT` des hooks (`crew_hook.py`, `spec_to_task_hook.py`) remonte à la racine git quand `CLAUDE_PROJECT_DIR` est un sous-dossier — plus de `crew/` fantôme créé dans `backend/`, `frontend/`, etc.

## [0.5.0] - 2026-10-22

- **`social` and `seo` personas** — organic social distribution and search/store/AI-answer discoverability, both read-only, dated sourcing, handing briefs to `comms`. `legal` now covers marketing moves (influence, contests, prospecting, comparative claims). Persona lists are derived by glob in `crew_update.py` and `verify_plugin_package.py`; descriptions are kept short.

## [0.4.0] - 2026-10-16

- **`/crew-version`** — prints the installed claude-crew version (`vX.X.X`).

## [0.3.1] - 2026-10-16

- **Session title** — `crew_hook.py` names the session after its task via the
  SessionStart `sessionTitle`.
- **`/crew-count`** — compact report with the terminal count and session titles.
- **README** — new « update » tutorial section.

## [0.3.0] - 2026-10-16

- **Portable `crew/dashboard.bat`** — now shipped in `template/crew/` (copied by
  `/crew-init`, kept current by `/crew-update`). It finds `server.py` via
  `%CREW_DASHBOARD_DIR%`, then the repo's `scripts/dashboard/`, then the highest
  installed plugin version in the Claude plugin cache; pauses on error when
  double-clicked. Previously it only worked inside the claude-crew repo.
  `.dashboard-venv/` added to the template `.gitignore`; `*.bat` forced to CRLF.
- **Token audit** — `crew_hook.py` gains read-only `next-task`, `count` and
  `status` commands (JSON). `/crew-start`, `/crew-count` and `/crew-status`
  now call them instead of re-deriving the logic in prose (`/crew-start`
  154 → ~85 lines, count/status ~600/340 → ~230/260 words). `/crew-start` no
  longer stops on a lock or zone collision: it skips that task and tries the
  next independent one. Parser: the « À classer » section is no longer
  swallowed by the last batch. `CLAUDE.md`: persona dispatch only when ≥2 real
  options (was « 1 % chance, non-negotiable »), review/simplify conditional on
  diff size, graphify block conditional, UI skill lines merged. Persona
  descriptions shortened.

## [0.2.2] - 2026-10-02

- **Fixed zone-overlap false positives** — `check_zone_overlaps` counted any
  batch with a task in `crew/TODO/` as active, so two never-started batches
  with touching `Zone :` lines raised `[zone]` warnings (or Stop blocks) every
  turn. Active now means a task in `CURRENT_TASKS/`/`PAUSED/` or held by a
  non-expired session lock (worktree-started tasks). A cross-session overlap
  only hard-blocks a session involved in it; an unrelated third session gets
  a warning instead of a Stop→reinvoke loop. The dashboard uses the same
  definition and no longer counts sessions older than the 6h TTL — 2026-10-02.
- **Fixed ghost sessions in `crew_lock.json`** — a task started and closed
  inside a batch worktree was never seen in the main checkout's
  `CURRENT_TASKS/`, so it never entered `finished` and its lock (and session
  entry) survived until the 6h TTL. `purge_closed_task_locks` now drops any
  locked task absent from both the main checkout and the session's worktree
  (TODO/CURRENT_TASKS/PAUSED) on each `Stop`; no-op when run from a
  worktree — 2026-10-01.

## [0.1.1] - 2026-08-22 (retroactive)

Everything up to and including this version predates this changelog — this
entry is a retroactive summary, not a per-task log. See
`crew/CLAUDE_CONTEXT/HISTORIQUE.md` for full task-level detail.

- **Renamed** `organized` → `crew` (folders, hooks, skills, docs) —
  2026-08-17.
- **Repackaged as a Claude Code marketplace plugin** — `template/`,
  `skills/`, `agents/`, `scripts/`, `hooks/hooks.json`,
  `.claude-plugin/{plugin,marketplace}.json`; `/crew-init` now reads from
  `${CLAUDE_PLUGIN_ROOT}/template/` instead of copying skills, agents, and
  hooks into the target project — shipped 2026-08-20, closed 2026-08-22.
- **Added local closure auto-commit** — `crew_hook.py` commits (local only,
  never pushes) the `crew/` scope of a finished task on session `Stop` —
  2026-08-22.
- **Added git-worktree batch isolation** — each active batch runs in its own
  worktree/branch, plus a hardened `PreToolUse` gate blocking
  `Edit`/`Write`/`MultiEdit`/mutating `Bash` on paths locked by another
  session — 2026-08-22.
- **Hardened batch-lock quick wins** — mutex around the lock file, a
  preventive `PreToolUse` gate before starting an uncategorized task, and a
  blocking zone-overlap check between sessions — 2026-08-22.

## [0.2.0] - 2026-08-25

- **Added `/crew-update`** — updates engine files (`CLAUDE.md`/`AGENTS.md`/
  `PRODUCT.md`/`CONTRIBUTING.md`/`SECURITY.md`/`check_placeholders.py`, plus
  `crew_hook.py`/`spec_to_task_hook.py`/local skills/agents on Option C
  installs) on an already-bootstrapped project, tracked via hashes in
  `crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json` — never touches `crew/` task
  data, never silently overwrites a personalized file. A file that vanished
  from the source (moved/removed upstream) is classified `removed` and
  never auto-applied. For legacy projects with no existing
  `SCAFFOLD_VERSION.json`, a `--seed`/`seed()` step lets the user explicitly
  trust the current local content as the baseline, so the first real run
  compares against actual upstream changes instead of flagging every
  drifted file as a conflict (`seed()` refuses to overwrite an existing
  baseline unless `force=True`/`--force` is passed explicitly). Install mode
  (legacy vs. plugin) is auto-detected (`detect_mode()`) rather than left to
  prose in the skill; `--legacy` remains available to force it.
- **Fixed** a worktree lock registration gap — a task's live lock is now
  registered preventively at the moment its file is `git mv`'d into a
  worktree, closing a race window where another session could start on the
  same zone before the lock was written.
- **Fixed** `CLAUDE_PROJECT_DIR` root resolution in `crew_hook.py`.
- **Added `/crew-count`** — read-only report of how many batches are
  launchable in parallel right now, distinct from batches already active or
  excluded for zone overlap.
- **Added the 150k-token context budget rule** — a `Stop`-hook check
  (`check_context_budget`) estimates session context usage from the
  transcript and warns (non-blocking) once the session looks past the
  threshold; recommends `/clear` or a new session instead of silently
  accumulating.
- **Added auto-pruning of fully-closed batches** — once every task in a
  batch in `CLAUDE_BATCH.md` is struck through, the hook removes the whole
  batch section on the next turn so the file doesn't grow unbounded; full
  history stays in `HISTORIQUE.md`.
- **Documented** the two-layer locking mechanism in the README.

## [0.2.1] - 2026-08-28

- **Fixed** `/crew-count` never shipping to installed plugins — the skill
  only existed under `.claude/skills/crew-count/` (local dev copy), never
  mirrored into the packaged `skills/crew-count/` that `plugin.json`
  actually ships. Copied it over; the command is now installed on
  update/reload like the other `/crew-*` skills.

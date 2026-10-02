# Changelog

All notable changes to the `claude-crew` scaffold are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
version numbers match the `version` field in
[`.claude-plugin/plugin.json`](./.claude-plugin/plugin.json) (see
[`CONTRIBUTING.md`](./CONTRIBUTING.md) for the bump convention).

## [Unreleased]

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

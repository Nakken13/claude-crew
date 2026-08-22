# Changelog

All notable changes to the `claude-crew` scaffold are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
version numbers match the `version` field in
[`.claude-plugin/plugin.json`](./.claude-plugin/plugin.json) (see
[`CONTRIBUTING.md`](./CONTRIBUTING.md) for the bump convention).

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

## [Unreleased]

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

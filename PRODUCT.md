# PRODUCT.md — crew-mates

## Vision

Claude Code forgets everything between sessions, and two sessions on the same
repo edit the same files with no warning. crew-mates gives a project a
file-based task lifecycle and deterministic collision prevention, so several
Claude Code sessions (and several developers) can work in parallel safely.

## Target user

Developers who run more than one Claude Code session on a repository, alone or
in a small team, and want their task state to live in plain, diffable Markdown
rather than a hosted board.

## Current scope

- Task lifecycle folders (`crew/PROBLEMS` → `TODO` → `CURRENT_TASKS` → `PAUSED` → history + tests).
- Batching with disjoint zones, per-batch `git worktree`, and a `PreToolUse` hook that blocks edits into a zone locked by another session.
- Opt-in team mode (`/crew-collab`): remote claims over the `refs/crew/claims` git ref.
- Adaptive test policy (`crew/CLAUDE_CONTEXT/TESTS_POLICY.md`).
- `/crew-*` skills, 8 specialist personas, 10 zero-token TypeScript mods, optional local dashboard.

## Out of scope (explicitly)

- A hosted board, accounts, or any service to run: the project is local-first and files-only.
- Telemetry or network calls (the only network use is the opt-in claims ref pushed to *your* remote).
- Preventing code merge conflicts between developers: claims prevent duplicate *work*, not conflicting *edits*.
- Changing the on-disk task format casually: existing projects must keep working across updates.

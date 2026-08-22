# Worktree isolation + hardened gate for batch anti-collision

## Goal

Today's batch-lock system (`crew_hook.py`) is cooperative and advisory: it
only intercepts one exact shell shape (`git mv crew/TODO/x.md
crew/CURRENT_TASKS/x.md`) and never gates `Edit`/`Write`/`MultiEdit` tool
calls at all. Two Claude Code sessions working the same project can still
silently overwrite each other's file edits if either of them writes through
any path the hook doesn't specifically watch.

Goal: guarantee that two sessions running `/crew-start` on different batches
can **never silently collide** on the same file — worst case is a visible,
blocking git merge conflict, never a lost or silently overwritten edit.

## Non-goals

- Not solving collisions *within* the same batch (two tasks in one batch are
  meant to be sequenced by one session — unchanged).
- Not adding a distributed lock service, external DB, or network dependency.
  Stays file-based, local-first, Windows-compatible (no `fcntl`).
- Not auto-resolving merge conflicts. A conflict stays a conflict — the
  system's job is to make sure it's the *only* failure mode, and that it's
  visible instead of silent.
- Not changing the task lifecycle (TODO → CURRENT_TASKS → HISTORIQUE) or the
  batching rules in `CLAUDE_BATCH.md` — this design sits underneath them.

## Architecture

Two layers, defense in depth:

**Layer 1 — physical isolation (hard guarantee).** Each *active* batch runs
in its own `git worktree` (separate directory on disk, dedicated branch
`crew/batch-<slug>`). Two sessions on two different batches are two
different directories — collision is physically impossible, not just
detected. The only remaining contact point is the merge back to `main` at
batch close, which is inherently visible and blocking on conflict.

**Layer 2 — hardened gate (safety net).** The existing `PreToolUse` hook
currently matches `Bash` only and looks for one `git mv` shape. It's
extended to match `Edit|Write|MultiEdit|Bash` and check the touched path
against zones locked by *another* session, read from `crew_lock.json`. This
covers any session that ends up writing outside its worktree (main checkout
used directly, an external script, a task not yet routed through
`/crew-start`).

Layer 1 is what makes the guarantee physical rather than advisory. Layer 2
exists because Layer 1 only applies to sessions that actually went through
the worktree flow — anything that bypasses it still needs a backstop.

## Components

### `crew_lock.json` (replaces `.batch_locks.json`)

One entry per **active session** (not per task slug, as today):

```json
{
  "sessions": {
    "<session_id>": {
      "batch": "Batch A — Auth",
      "tasks": ["auth-refactor.md"],
      "worktree": "../claude-crew-batch-auth",
      "branch": "crew/batch-auth",
      "since": "2026-08-22T14:00:00"
    }
  }
}
```

- `tasks` mirrors the current per-slug lock set (used by
  `check_batch_collisions` / zone-overlap logic), now nested under the
  session that holds them instead of being the top-level key. This keeps the
  existing collision-detection functions (`check_batch_collisions`,
  `check_zone_overlaps`, `_section_lock_sessions`) working against the same
  shape of data (slug → session_id), just derived from `sessions[*].tasks`
  instead of read as a flat map.
- Written under the existing `LocksMutex` (unchanged: atomic
  `O_CREAT|O_EXCL` marker file, TTL-based staleness recovery, best-effort
  2s wait, never blocks the turn).
- Same TTL purge as today (6h) — a session's entry (and everything it holds:
  task locks + worktree registration) is purged together if stale.
- `BATCH_LOCKS.md` regeneration (human-readable live view) keeps its current
  format; gains a `worktree` column when present.

### Worktree lifecycle

- Created by `/crew-start` (the `manager` persona step), not by the hook —
  the hook only ever reacts to state, it doesn't drive workflow.
- Location: `../<repo-name>-batch-<slug>/`, sibling to the main checkout.
  Chosen over a subdirectory so it's trivially `.gitignore`-free (worktrees
  under the repo root need explicit ignoring; siblings need none).
- Branch: `crew/batch-<slug>`, created off current `main` HEAD.
- Reused (not recreated) if the batch already has one — covers `/crew-start`
  resuming a batch that's already in progress from a previous turn or a
  second task in the same batch.
- The running session then treats the worktree as home for the rest of the
  turn: a `cd` into it (Bash tool working directory persists across calls
  within a session) plus absolute paths for `Read`/`Edit`/`Write` pointed at
  the worktree copy of each file, not the main checkout's.

### Hardened `gate_pretooluse`

- Matcher list grows from `Bash` to `Bash|Edit|Write|MultiEdit`.
- For `Edit`/`Write`/`MultiEdit`: extract `file_path` from `tool_input`
  directly (no shell parsing needed — these tools already give a structured
  path).
- For `Bash`: keep today's `git mv` extraction, add a generic "does any
  token look like a path under a locked zone" scan for other
  file-mutating shell commands (`rm`, `mv`, `cp`, redirection `>`) as
  best-effort — same spirit as `_extract_git_mv_task`, not a full shell
  parser.
- Check: does the path fall under a `Zone:` path owned by a batch section
  that's currently locked (in `crew_lock.json`) by a session other than the
  caller? If yes → `exit(2)` with a clear message naming the batch and the
  other session. If the path isn't under any declared zone, or the zone's
  lock is unowned/owned by the same session → allow (unchanged
  fail-open-to-uncategorized behavior, consistent with today's design).

## Data flow

1. `/crew-start` picks a batch (existing `manager` anti-collision check,
   unchanged) → ensures worktree exists for it → registers the session in
   `crew_lock.json` (batch, tasks, worktree, branch, timestamp) under
   `LocksMutex` → `cd`s into the worktree.
2. Every turn's `Stop` hook: same regen/journal logic as today, plus
   refreshing this session's `since` timestamp in its `crew_lock.json`
   entry (keeps it alive against the TTL purge) and re-deriving the
   slug→session_id view from `sessions[*].tasks` for the existing
   collision/zone-overlap checks — those functions don't change, only what
   feeds them does.
3. Every `Edit`/`Write`/`MultiEdit`/`Bash` call: `gate_pretooluse` reads
   `crew_lock.json` (no mutex needed — read-only), checks the path against
   locked zones of other sessions, blocks or allows.
4. `/crew-close-task` (batch fully done): rebase `crew/batch-<slug>` onto
   current `main`, fast-forward merge if clean, remove worktree + branch,
   drop the session's entry from `crew_lock.json`.

## Error handling

- **Merge conflict at close:** no auto-resolution. Abort the merge, leave
  worktree + branch intact, surface the conflicting files to the user.
  Still remove the session's `crew_lock.json` entry (its work is done, even
  if integration isn't) so it stops occupying the zone lock for other
  sessions waiting on the same batch's neighbor tasks.
- **Session crash (no clean `/crew-close-task`):** existing TTL purge (6h)
  removes the stale `crew_lock.json` entry. The worktree itself is *not*
  auto-deleted (might hold uncommitted work) — `/crew-status` gains a
  warning line for worktrees with no matching active session entry, left
  for manual cleanup.
- **Two sessions resume the same batch:** same rule as today's
  `_claim_resume_lock` — second session attempting to claim a batch whose
  worktree/lock is already held by another `session_id` is blocked
  (`exit(2)`) before it starts editing.
- **No git remote (plugin used in a local-only repo):** rebase step targets
  local `main` only, no `fetch` attempted. Documented as a constraint, not
  silently skipped.
- **Gate false positive (path scan misses a rename/symlink trick):** stays
  fail-open on ambiguity, consistent with the existing hook's "never break
  the turn on internal error" contract — Layer 2 is a safety net on top of
  Layer 1's physical guarantee, not the sole line of defense.

## Versioning

This changes the on-disk format from `.batch_locks.json` (flat
slug → session map) to `crew_lock.json` (session → {batch, tasks, worktree,
branch} map). No migration needed: it's a live, ephemeral state file (TTL
6h, regenerated every turn) — on upgrade, any stale `.batch_locks.json` is
simply ignored/deleted; `crew_lock.json` starts empty and rebuilds itself
from the next `/crew-start`.

Ships identically in both copies of the hook (`crew/crew_hook.py` for this
project, `scripts/crew_hook.py` for the plugin) — this project's copy stays
the reference implementation, `scripts/crew_hook.py` gets resynced from it
as the last step, same as prior batch-lock hardening rounds.

## Testing

- `crew/TESTS/IA/worktree-batch-isolation.md`:
  - `/crew-start` on two different (non-overlapping-zone) batches from two
    simulated sessions → two worktrees created, each session's file edits
    land only in its own worktree directory (assert zero shared files
    written outside each worktree).
  - `/crew-close-task` with a clean rebase → fast-forward merge succeeds,
    worktree + branch removed, `crew_lock.json` entry cleared.
  - `/crew-close-task` with a conflicting change on `main` → merge aborts,
    worktree + branch survive, conflict surfaced, `crew_lock.json` entry
    still cleared.
  - Hardened gate: `Edit` tool call targeting a path inside a `Zone:`
    locked by another session's `crew_lock.json` entry → blocked
    (`exit(2)`); same path with no active lock or locked by the caller's
    own session → allowed.
  - TTL purge: session entry older than 6h removed on next `Stop`;
    `/crew-status` flags the now-orphaned worktree.
  - Resume collision: second session attempting `/crew-start` on a batch
    already claimed (worktree + lock held by another `session_id`) is
    blocked before any edit.
- `crew/TESTS/DEV/worktree-batch-isolation.md`: manual two-terminal run —
  open two real Claude Code sessions, `/crew-start` on two different
  batches simultaneously, confirm no cross-contamination and a clean merge
  path for both at close.

## Out of scope / follow-ups

- Automatic conflict resolution or AI-assisted merge conflict summarization
  — flagged as a possible follow-up, not required for the 100% guarantee
  (a visible conflict already satisfies "no silent collision").
- Cleaning up orphaned worktrees automatically — deferred, since it risks
  discarding uncommitted work; stays a manual step surfaced by
  `/crew-status`.
- Cross-machine / cross-repo-clone session coordination (this design
  assumes all sessions operate against the same local repo + its
  worktrees, not multiple independent clones).

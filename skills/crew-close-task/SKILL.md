---
name: crew-close-task
description: Closes a finished crew task — checks the boxes, runs review + simplify passes (above the threshold), writes the history entry, produces the AI/DEV test checklists according to the project's test policy, strikes the task out of its batch. Also triggers on — "/crew-close-task", "cette tâche est finie", "clôture la tâche", "this task is done", "close the task".
---

Run the protocol defined in `crew/CLAUDE_CONTEXT/LIFECYCLE.md` § "Task management" (item
3) — skip no step. The passes in step 3 and the tests in step 5 follow their
thresholds; modularity is always required (see `crew/CLAUDE_CONTEXT/AGENTS.md`
if this project documents specific anti-patterns).

**Repo-root anchoring is mandatory**: every `crew/...` path in this skill is
resolved **from the repo root**, never from the current cwd. In a single-subtree
session (see `crew/CLAUDE_CONTEXT/LIFECYCLE.md` § Segmented AGENTS.md guides), the cwd
may be a subfolder — a relative `crew/...` path written as-is would create a
duplicate phantom `crew/` there instead of touching the root. Resolve the root
once at the start (`git rev-parse --show-toplevel` or equivalent) if it is not
already known — no need to re-check on every following `Read`/`Write`/`Edit`/`Bash`.

## Steps

1. Identify the relevant `crew/CURRENT_TASKS/<slug>.md` file (ask which one if
   several tasks are active and the user did not say).
2. Check that **all** `- [ ]` actions in the file are ticked `- [x]`. If not →
   **do not continue**: list the remaining actions and stop there.
3. Passes before closing, **if the diff exceeds the threshold in the
   `CLAUDE.md` routing** ("End of task"; same for every level of
   the test policy):
   - Skill `requesting-code-review` on the code touched by the task.
   - Skill `simplify` on the same scope — covers reuse, simplification,
     efficiency **and** modularity (no catch-all file, no logic duplicated in
     2+ places without extraction).

   Below this threshold: `verification-before-completion` is enough; modularity
   is still required.
4. **Commit the implementation**, once the step 3 passes are done and their
   feedback applied: `git status` to identify the files actually modified by
   **this task** (the one being closed — not another task lingering in parallel
   in the same checkout). Cross-check this list against the `Zone :` already
   declared for this task in `crew/CLAUDE_BATCH.md`: a file outside this zone
   must never be added without checking — when in doubt, ask rather than
   silently include it. Then `git add -- <these files>` and `git commit --
   <these files>` (the scoped `git add` is needed for newly created files, which
   `git commit --` alone does not stage; never `-A`/`git add .`, never a bare
   `git commit`, never push). Distinct from and complementary to the automatic
   crew/ bookkeeping commit (step 5 below,
   `crew/crew_hook.py::auto_commit_closure`): do not recommit here the
   bookkeeping paths (`crew/CURRENT_TASKS/<slug>.md`, `HISTORY.md`, `TESTS/`,
   `CLAUDE_BATCH.md`, `INDEX.md`) already handled by that separate mechanism.
   Purely bookkeeping/crew doc task (no implementation file touched outside
   crew/) → explicit no-op: say so ("nothing to commit here").
5. Once the implementation commit is done (or its no-op noted):
   - **Decide the tests** (before writing the `HISTORY` entry, which carries
     the verdict): read `crew/CLAUDE_CONTEXT/TESTS_POLICY.md` and apply its
     level, grid, hesitation protocol and box cap — that file is the only source
     of these rules. **Missing** → project not yet migrated: historical behavior
     (`full`), nothing changes silently; add to the final report "Test policy
     missing: `/crew-update` to enable it".
   - If a checklist is decided: create `crew/TESTS/IA/<slug>.md` and/or
     `crew/TESTS/DEV/<slug>.md` according to the sorting criterion in
     `CLAUDE.md` (🤖/🔍 = the AI can run it alone; 🖱️ = a human action is really
     needed). Do not tick these tests at creation — validation is for a later
     session.
   - Delete `crew/CURRENT_TASKS/<slug>.md`.
   - Add an entry to `crew/CLAUDE_CONTEXT/HISTORY.md`: what, when, key
     files/commits, and the tests verdict defined by the policy (omitted for
     `none`).
   - Strike the task's line in `crew/CLAUDE_BATCH.md` (`~~`slug.md`~~`, in its
     batch or in the `Unsorted` section) — **never delete the
     line**: `prune_closed_batches` (`crew/crew_hook.py`) only removes a batch
     when all its referenced tasks are struck; a line deleted instead of struck
     leaves an orphan batch header that the automatic purge never detects.
5bis. **Release the remote claim** (opt-in: only if
   `crew/CLAUDE_CONTEXT/CREW_CONFIG.md` contains `remote_claims : true`,
   otherwise skip): `python "$HOOK" claims release <slug>.md --done` (`$HOOK`:
   see `/crew-start` step 1; removes the entry from the ref: the task is
   finished). Offline or failure → non-blocking: report that the claim will
   expire on its own (8 h TTL) or to retry later.

6. **Integrate the batch worktree**, if the session works from a
   `../<repo-name>-batch-<slug>/` worktree on the `crew/batch-<slug>` branch
   (physical isolation set up by `/crew-start`, see
   `docs/superpowers/specs/2026-08-22-worktree-batch-isolation-design.md`):
   - If **other tasks of the same batch** remain in `crew/CURRENT_TASKS/` (batch
     not fully finished) → do not touch the worktree, it is still in use. Stop
     there for this section.
   - Otherwise (batch fully finished): `git rebase main` on the
     `crew/batch-<slug>` branch (strictly local rebase — no `git fetch`, no
     remote is assumed to exist).
     - Clean rebase → fast-forward merge into `main`, then
       `git worktree remove ../<repo-name>-batch-<slug>` and
       `git branch -d crew/batch-<slug>`. `cd` back to the main checkout before
       continuing.
     - Rebase conflict → `git rebase --abort`, leave the worktree and branch
       intact, list the conflicting files to the user for manual resolution. Do
       not try to remove the session entry from `crew_lock.json` by hand:
       `crew/crew_hook.py` already cleans it up on its own (Stop/SessionEnd) —
       the code work is done even if the integration is not yet.
7. Report: implementation files/commit (step 4, or its noted no-op), what was
   written to history, test files created (IA/DEV), batch updated, and the fate
   of the batch worktree (kept because batch not finished / merged and removed /
   conflict left for manual resolution).

## What this skill does not do

- Never ticks actions on the user's behalf to close faster — if actions remain
  unticked, it stops and says so.
- Never skips `requesting-code-review`/`simplify` above the step 3 threshold, nor
  the modularity requirement below it.
- Does not generate a checklist "by reflex": `TESTS_POLICY.md` decides.
- Does not default a test to `IA/` — applies the real criterion (does the AI
  have what it needs to run it itself?), not convenience.
- Never deletes a batch worktree/branch while another task of the same batch is
  still in `crew/CURRENT_TASKS/`.
- Never resolves a rebase conflict automatically — aborts cleanly and reports
  it, never discards the worktree's work.
- Never commits the implementation outside the step 4 scoping (never a bare
  `git commit` or `git add -A`/`git add .`).

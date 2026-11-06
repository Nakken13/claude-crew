---
name: crew-start
description: Resumes crew work without saying which task — continues the task in CURRENT_TASKS, otherwise starts an inactive batch from TODO (anti-collision), then codes. Also triggers on — "/crew-start", "continue le travail", "lance la suite", "continue the work", "start the next task".
---

Single entry point to resume a crew session without naming a task. The task
**choice** is made by a deterministic script (`crew_hook.py next-task`); this
skill then runs the start (lock, worktree, `git mv`), the implementation, then
`/crew-close-task`.

**Repo-root anchoring is mandatory**: every `crew/...` path is resolved from the
repo root (`git rev-parse --show-toplevel`), never from the current cwd
(otherwise a phantom `crew/` is created in a subfolder). The
`git worktree add`/`cd` of steps 3-4 runs from the root of the main checkout.

## Steps

1. **Choose the task** (read-only, ~0 reasoning tokens):

   ```bash
   ROOT="$(git rev-parse --show-toplevel)"
   HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
   CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" next-task
   ```

   (plugin: the plugin's `scripts/crew_hook.py`; manual clone:
   `crew/crew_hook.py`). JSON output: `action`, `task`, `batch`,
   `worktree`, `branch`, `skipped[{slug,reason}]`, `paused`,
   `unclassified`, `ambiguous`. It already covers: other sessions' locks,
   active/paused batches, `Zone :` overlap, ICEBOX and `À classer` (to be
   sorted) ignored. Do not redo this sorting by hand.

   If `paused` is not empty, flag it to the user (task + what blocks it) — a
   `PAUSED/` task is NEVER resumed automatically.

2. **According to `action`**:
   - `resume` → step 3 (resume case). If `ambiguous`: ask the user which one to
     prioritize rather than guess.
   - `start` → step 3 (start case).
   - `classify` → `TODO/` tasks have neither batch nor zone (`unclassified`):
     dispatch `Agent({subagent_type: "manager"})` to classify them (impact zone +
     batch, see `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md` § Batching), then rerun
     step 1.
   - `none` → nothing startable: tell the user why from `skipped` (lock, active
     batch, overlap) or "TODO empty", and stop. The only case where the skill
     stops without having coded.

2bis. **Remote claim** (opt-in: only if `crew/CLAUDE_CONTEXT/CREW_CONFIG.md`
   contains `remote_claims : true`, otherwise skip; claims are a layer shared
   between devs on the `refs/crew/claims` ref, see `AGENTS.md`):
   - if `action: start` and the task does not exist locally but is listed in
     `remote_todo`: `python "$HOOK" claims materialize <task>` (writes the `.md`
     into `crew/TODO/` from the ref);
   - set the claim before any move:
     `python "$HOOK" claims claim <task> --session "$CLAUDE_CODE_SESSION_ID" --batch "<batch>" --branch "<branch>" --zone "<zone from the JSON, comma-separated>"`;
   - **on resume (`action: resume`) redo this same claim**: it refreshes `ts`
     (the TTL is 8 h, a long task would otherwise become claimable again) and
     publishes a task started offline;
   - `ok: false` (already taken, overlapping zone, conflict) → do not insist:
     rerun step 1 (the script sees the claim and suggests the next one);
   - `offline` / `claims_warning` → **non-blocking**: continue and flag it to the
     user ("remote claims not verified").

3. **Lock + isolation** (before any edit):
   - *Resume*: run `Bash({command: ': "crew-resume:<task>"'})` (a no-op that sets
     the lock through the `PreToolUse` hook).
   - Create or reuse the batch worktree:
     `git worktree add -b <branch> <worktree> main` (values from the JSON;
     `git worktree list` first: if it already exists, do not recreate it,
     including under an old `…-batch-<slug>-…` slug). `cd` into it and use
     absolute paths of this copy for every following `Read`/`Edit`/`Write`.
   - *Start*: from the worktree,
     `git mv crew/TODO/<task> crew/CURRENT_TASKS/<task>`, update both
     `INDEX.md` files.

   - *Name the session* (start only; on resume the SessionStart hook already did
     it): show the user `/rename <task slug without .md>` — a hook cannot rename
     a running session, only SessionStart can.

4. **The hook blocks (exit 2)** — lock taken or batch busy between the choice and
   the claim (race between sessions): do not insist. Rerun step 1 (the script now
   sees the lock and suggests the next task). Only stop on `action: none`.

5. **Implement**: reread the task file, work through the `- [ ]` actions in
   order, with the skills from the `CLAUDE.md` routing
   (`test-driven-development`, `systematic-debugging`, `graphify`…). Tick each
   action when it is really finished (not ahead of time, not in bulk).

6. All actions ticked → chain straight into `crew-close-task` (without asking
   for confirmation, it is part of the protocol).

## What this skill does not do

- Never starts two tasks from different batches in the same invocation — one
  `/crew-start` = one task until its closure (or a real blocker).
- Never picks from `crew/ICEBOX/` nor from `À classer` (to be sorted) without
  classification by `manager`.
- Never automatically resumes a task from `crew/PAUSED/`.
- Does not tick unfinished actions, does not skip the lock/anti-collision.
- Does not replace `/crew-close-task` — calls it at the end of the task.

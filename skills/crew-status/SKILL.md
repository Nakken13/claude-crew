---
name: crew-status
description: Read-only report of the crew state — active batches and zones, tasks in progress, unticked AI tests, unclassified TODO. Also triggers on — "/crew-status", "où en est le projet", "état des batchs", "project status", "batch status".
---

Read-only — modifies no file. The computation is done by a deterministic script;
this skill presents its result. Complements the `Stop` hook (discreet stderr
output) with an on-demand view.

1. Run (plugin: the plugin's `scripts/crew_hook.py`; manual clone:
   `crew/crew_hook.py`):

   ```bash
ROOT="$(git rev-parse --show-toplevel)"; HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" status
```

2. Report, from the JSON:
   - `active_batches` + `zone`; any `zone_overlaps` = **violated invariant**, to
     flag explicitly (batches + paths), not just list;
   - `current`: `done/total` ratio per task;
   - `paused`: tasks waiting for visual/dev validation — flag by name, not
     counted as normal work in progress;
   - `tests_ia_unchecked`: files with unticked boxes (what remains to validate);
   - `todo_orphans`: in `TODO/` but absent from `CLAUDE_BATCH.md` (neither batch
     nor `Unsorted`, the to-be-sorted section) → suggest `/crew-new-task` /
     `manager`;
   - `bootstrap_pending` true: run `python check_placeholders.py` and include its
     result (`<...>` placeholders = scaffold not initialized → `/crew-init`);
   - **Never-ticked checklists guard** (suggestion only): read the `Level:`
     line (legacy projects: `Niveau :`) of `crew/CLAUDE_CONTEXT/TESTS_POLICY.md` (`grep`, without reading the
     file). Only if the level is `full`, or the file is missing or unreadable
     (historical `full` behavior): if the `- [ ]` in `crew/TESTS/{IA,DEV}`
     (excluding `TESTS_DONE`) clearly dominate the `- [x]` (totals via
     `grep -rhF … | wc -l`), suggest "N boxes never ticked: switch to `light` in
     `TESTS_POLICY.md`?". Never at `light`/`none`, never modify the file.
   - `orphan_worktrees`: a `*-batch-*` worktree on disk with no session carrying
     it (crash, or `/crew-close-task` never run) — flag it for manual cleanup
     (`git worktree remove` / `git branch -d` by the user), **never** delete it
     yourself (possible uncommitted work).

## What this skill does not do

- Writes, moves, ticks nothing — pure reporting.
- Does not replace `/crew-new-task` / `/crew-close-task` to act.

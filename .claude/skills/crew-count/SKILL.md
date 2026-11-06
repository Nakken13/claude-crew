---
name: crew-count
description: Read-only report — how many CLAUDE_BATCH.md batches can be launched in parallel (active, launchable, excluded for overlap). Also triggers on — "/crew-count", "combien de Claude en parallèle", "how many Claudes in parallel".
---

Read-only — modifies no file. The computation is done by a deterministic script;
this skill only presents its result.

1. Run (plugin: the plugin's `scripts/crew_hook.py`; manual clone:
   `crew/crew_hook.py`):

   ```bash
ROOT="$(git rev-parse --show-toplevel)"; HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" count
```

   JSON output: `launchable_count`, `launchable[]` (`name`, `zone`, `remaining`,
   `task` = session title), `active[]`, `excluded[]`, `placeholders[]` and
   **`report`**: already-rendered markdown text (exact number + title/batch/zone
   table + active/excluded in one line).

2. Answer by displaying **`report` as is**, nothing else (no rewording, no
   reminder of the rules). Each title in the "Session title" (session title)
   column is the slug of the task to give the terminal (`/rename` or first
   message); `/crew-start` resumes it.

## What this skill does not do

- Writes nothing, starts no task (user's decision or `/crew-start`), does not
  recategorize `Unsorted`.

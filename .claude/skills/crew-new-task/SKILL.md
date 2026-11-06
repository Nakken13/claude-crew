---
name: crew-new-task
description: Creates a crew task (TODO or CURRENT_TASKS) with its file, INDEX.md and batching through the manager persona. Also triggers on — "/crew-new-task", "crée une tâche", "ajoute au backlog", "découpe ça en tâches", "create a task", "add to the backlog", "break this into tasks".
---

This skill encodes the task-creation protocol already defined in
`crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md` (§ Task management, § Batching) — it
does not replace that document, it saves rewriting a long prompt by hand each
time. Single source of truth = `CLAUDE.md`; this file only standardizes the call.

**Repo-root anchoring is mandatory**: every `crew/...` path in this skill is
resolved **from the repo root**, never from the current cwd. In a single-subtree
session (see `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md` § Segmented AGENTS.md guides), the cwd
may be a subfolder — a relative `crew/...` path written as-is would create a
duplicate phantom `crew/` there instead of touching the root. Resolve the root
once at the start (`git rev-parse --show-toplevel` or equivalent) if it is not
already known — no need to re-check on every following `Read`/`Write`/`Edit`/`Bash`.

## What this skill does

1. Gather the available context on the request: what, why, known technical
   context (files/screens/modules concerned if identifiable, cross-repo
   dependencies if this project has any — separate backend/frontend repo, shared
   service), and whether the task starts right away (`CURRENT_TASKS/`) or goes to
   the backlog (`TODO/`).
2. If the `manager` persona is available (provided by the plugin via
   `agents/manager.md`, or locally via `.claude/agents/manager.md`): dispatch
   **a single** `Agent({subagent_type: "manager"})` with a prompt that
   explicitly covers, in order:
   - description of the feature/task + context (why, known dependencies);
   - breakdown into concrete (not vague) tickable `- [ ]` actions;
   - where the file is born (`crew/TODO/<slug>.md` or
     `crew/CURRENT_TASKS/<slug>.md`);
   - update of the `INDEX.md` of the relevant folder;
   - categorization in `crew/CLAUDE_BATCH.md`: impact zone, attachment to an
     existing batch if overlapping, otherwise a new batch or the `À classer`
     (to be sorted) section; check the disjointness invariant between active
     batches;
   - explicit instruction: touch no file outside `crew/`.
   If the `manager` persona does not exist in this project (partial scaffold),
   run the same steps directly following `CLAUDE.md`.
2bis. **Remote claims** (opt-in: only if `crew/CLAUDE_CONTEXT/CREW_CONFIG.md`
   contains `remote_claims : true`, otherwise skip):
   - **before** dispatching `manager`: `python "$HOOK" claims check-dup --title "<title>" --zone "<zones>"`
     (`$HOOK`: see `/crew-start` step 1). If `duplicates` is not empty, show them
     to the user (title, holder, reason) and ask whether it is a duplicate
     before creating; Claude judges the semantic duplicate;
   - **after** the file is created: publish the entry so other devs see it
     without a push: `python "$HOOK" claims publish <slug>.md --title "<title>" --zone "<batch zones>" --body-file crew/TODO/<slug>.md`;
   - `offline` or failure → **non-blocking**: the task stays created locally, flag
     it (it will only be visible to others after a push or republication).

3. Report to the user: path of the created file, summary of the tickable
   actions, landing batch/section, and any external dependency (cross-repo,
   sequencing) flagged.

## Prompt template for the manager agent

```
New task to add to the crew backlog.

<description of the feature/problem, context, why>

Known technical context:
<files/modules concerned if known, cross-repo dependencies if this project
has any, existing crew tasks to look at for a similar convention/infra>

Apply the standard lifecycle (already in your role): file in
crew/TODO/ or crew/CURRENT_TASKS/, concrete tickable `- [ ]` actions,
INDEX.md up to date, CLAUDE_BATCH.md categorization (impact zone, existing
or new batch, disjointness invariant), nothing outside crew/.

Report: path of the created file, summary of the tickable actions chosen,
and landing batch/section in CLAUDE_BATCH.md.
```

## What this skill does not do

- Does not decide business priority/scope in place of the `ceo` persona (if it
  exists in this project) — if the request is an ambiguous product decision
  rather than a pure breakdown, route to `ceo` first.
- Never writes code — only `crew/` files.
- Does not duplicate an existing task: check `crew/TODO/INDEX.md` and
  `crew/CURRENT_TASKS/INDEX.md` first.

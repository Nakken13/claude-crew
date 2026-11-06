---
name: crew-update
description: Updates the engine files of a bootstrapped project to the latest scaffold version, without touching data or overwriting a customized file. Also triggers on — "/crew-update", "mets à jour le scaffold", "update the scaffold".
---

This skill runs `crew/crew_update.py` (or `scripts/crew_update.py` in plugin
mode — same module, two copies like the other engine files of this repo). It
never replaces a file without explicit confirmation.

## Install-mode detection

1. `detect_mode(project_root)` (in the module, not just in prose here — a single
   source of truth) looks for `.claude/skills/crew-init/SKILL.md` in the target
   project:
   - **Present** → `"legacy"` (Option C / manual clone, pre-plugin):
     `ENGINE_FILES_LEGACY` (`crew_hook.py`, `spec_to_task_hook.py`,
     `.claude/skills/crew-*/SKILL.md`, `.claude/agents/*.md`) is included in the
     update automatically, on top of the common files. The `--legacy` CLI flag
     forces this inclusion if detection is wrong.
   - **Absent** → `"plugin"`: do NOT try to sync skills/agents/hooks (they
     already run from the installed plugin and update through
     `/plugin update crew-mates` — say so explicitly to the user). Only the
     `ENGINE_FILES_COMMON` files are checked.
   - `plan()`/`--project` work in both cases with no manual intervention; only
     ask the user if the final report shows an unexpected result (e.g.
     `removed` on all of `ENGINE_FILES_LEGACY` while the project looked legacy).

## Seeding (legacy project with no history)

2. If `crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json` does not exist yet in the target
   project (first `/crew-update` of a project bootstrapped before this mechanism
   existed), every file that differs from the source comes out as `conflict` for
   lack of a recorded hash proving it is uncustomized — so nothing will be
   applied automatically on the first run. Offer via `AskUserQuestion` to seed
   the baseline first: "Accept the current local content as uncustomized since
   our last write?" (`seed(project_root, whitelist, version)`, or
   `python crew_update.py --project <dir> --seed --source-version <version>
   [--legacy]`). This is an explicit trust choice — if the user declines, treat
   each differing file as a normal `conflict` (manual resolution one by one, see
   the Confirmation section below) without seeding. `seed()` by construction
   refuses to overwrite an already recorded `SCAFFOLD_VERSION.json` (raises an
   error) — only pass `force=True` / `--force` if the user explicitly asks to
   re-seed the baseline on purpose (e.g. after a massive manual conflict
   resolution to be frozen as the new starting point).

## Source resolution

3. Scaffold source version = the `version` field of `.claude-plugin/plugin.json`
   if reachable (installed plugin or clone of the scaffold repo); otherwise ask
   the user for the source path (local clone of the scaffold, or the
   `${CLAUDE_PLUGIN_ROOT}` path) — never guess a version number.

## Plan (dry-run, never write at this stage)

4. Call `plan(project_root, source_root, whitelist)` (direct import of the
   `crew_update` module, or `python crew_update.py --project <dir> --source <dir>
   [--legacy]` from the CLI). Show the result grouped by status:
   - `up_to_date` — nothing to do, do not list in detail (just a count).
   - `new` — file added on the source side, missing locally → will be created.
   - `apply` — file unchanged since the last known write, source has evolved →
     will be updated with no risk of loss.
   - `conflict` — file modified locally since the last known write → **will
     never be silently overwritten**. Show a diff (or at minimum both hashes +
     the first differing lines) for each.
   - `removed` — still present locally but gone from the source (moved or
     deleted upstream) → **never applied automatically** (nothing to copy). Flag
     it to the user for a manual decision: check whether the file was moved
     elsewhere in the source before deleting it yourself, never delete it
     silently.

### Special case: slimmed `CLAUDE.md` (opt-in)

Since the template slimming, an older-generation `CLAUDE.md` remains **valid**:
the skills point to `crew/CLAUDE_CONTEXT/LIFECYCLE.md` (`§ Batching`, `§ Task management`,
`§ Segmented AGENTS.md guides`, `§ 2bis`), an engine file added by `/crew-update`; the old
long `CLAUDE.md` stays valid (those sections are in it too).

- `apply` → no risk; `conflict` (customized) → **never touched by default**, the
  report only flags "slimmed version available". Migration **only on explicit
  request**.
- If migration is requested (**manual** flow, `crew_update.py` has no dedicated
  mode): write `CLAUDE.md.new`, keep `CLAUDE.md.bak`, show the diff, list the
  local sections absent from the template (project rules to re-inject by hand).
  Nothing is applied without confirmation.
- Check that the mandatory anchors are present in the result: anti-collision,
  1% personas clause, the 100-line rule, 150k/100k thresholds, root-anchored
  `crew/`.
- Never remove a `§` pointer from the skills while derived projects may carry the
  old version.

## Mandatory confirmation

5. **Never call `apply()` without explicit confirmation.** Use `AskUserQuestion`:
   present the summary (count per status + list of `apply`/`new`/`conflict`
   files), offer at minimum "Apply `apply`/`new`, keep the `conflict` files as
   they are" / "Cancel". For each `conflict` file, the user can choose "keep my
   version" (skip, default behavior) — a guided manual merge (show the diff, let
   the user edit) remains possible but is never automatic.

## Apply

6. On confirmation: call `apply(project_root, source_root, decisions)` then
   `record_version(project_root, source_version, decisions)` — bumps the version
   recorded in `crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json` only for the files
   actually applied (`conflict` files keep their previously recorded hash, so
   they will be offered again at the next `/crew-update` until the user resolves
   them).
7. If only part of the files were applied (some `conflict` files remain), say so
   explicitly in the final report: the recorded version advances anyway (it
   reflects "what we could sync"), but some files are still waiting for manual
   resolution.

## Double hook (plugin + local copy)

8. `detect_double_hook(project_root)` (called at the top of `_main()`, read-only)
   flags a project where the `crew-mates` plugin is active (`enabledPlugins` of
   the project or of `~/.claude/settings.json`) AND whose
   `.claude/settings.json`/`settings.local.json` also call the local copy
   `crew/crew_hook.py`: two hooks on the same `crew_lock.json`, potentially
   diverging logic. A legacy project **without** an active plugin is normal, not
   flagged.
   - By default: warning (duplicated events + commands) and an offer to remove,
     **no modification**.
   - Removal only on explicit user confirmation: rerun with
     `--remove-double-hook` (removes only those hook entries, the rest of the
     settings is kept, but the file is reformatted as indented JSON).

## Test policy (existing projects)

8bis. If `crew/CLAUDE_CONTEXT/TESTS_POLICY.md` is **missing**, offer to create it
   — never silently — through a dedicated `AskUserQuestion`, separate from the
   step 5 confirmation. Content: the template
   `${CLAUDE_PLUGIN_ROOT}/template/crew/CLAUDE_CONTEXT/TESTS_POLICY.md` (manual
   clone: `<source>/template/...`), with level and risky zones inferred from
   `CLAUDE.md`, `README`, the manifests and targeted `grep`s in `HISTORY.md`
   (never read in full). The file is **not** in `ENGINE_FILES_*`: once created
   it belongs to the user. Declined → nothing is created; the skills keep the
   historical behavior (`full`).

## Remote claims (existing projects)

8ter. If `crew/CLAUDE_CONTEXT/CREW_CONFIG.md` is **missing**, create it from
   `${CLAUDE_PLUGIN_ROOT}/template/crew/CLAUDE_CONTEXT/CREW_CONFIG.md` (manual
   clone: `<source>/template/...`), with `remote_claims : false`: a solo project
   keeps exactly its behavior, nothing is synced until the dev flips the line to
   `true`. No question asked (the default is inert). An existing file is
   **never** modified; it is not in `ENGINE_FILES_*`.

## Migrate to the English names (optional)

Projects created before the English names existed keep working: the engine reads both. To move one over
(`HISTORIQUE.md` → `HISTORY.md`, `HISTORIQUE_ARCHIVE.md` → `HISTORY_ARCHIVE.md`, `CHANGELOG_TACHES.md` →
`TASK_CHANGELOG.md`, `CYCLE_DE_VIE.md` → `LIFECYCLE.md`, `## À classer` → `## Unsorted`, `Niveau :` →
`Level:`, `Zones risquées :` → `Risky zones:`, plus the references in `CLAUDE.md`, `AGENTS.md` and `.gitignore`),
only when the user asks:

1. Dry-run: `python <crew_update.py> --project "$ROOT" --migrate-names` and show the list (renames, rewrites,
   conflicts). A conflict means both names exist: never merge them automatically.
2. Warn: every collaborator must update crew-mates first (an older version does not know the English names and
   would recreate the French files). Ask for confirmation via `AskUserQuestion`.
3. Apply with `--apply` (uses `git mv` for tracked files), then tell the user to commit the renames.

## Report

9. Final summary: files created, files updated, files left in conflict or
   `removed` (reminding that they will be offered again at the next
   `/crew-update` until resolved), newly recorded version, and whether the test
   policy was created (level + zones, editable in `TESTS_POLICY.md`).

## What this skill does not do

- Never writes into `crew/TODO/`, `crew/CURRENT_TASKS/`, `crew/PROBLEMS/`,
  `crew/ICEBOX/`, `crew/TESTS/`, `crew/CLAUDE_CONTEXT/HISTORY.md`,
  `crew/CLAUDE_CONTEXT/TESTS_DONE/`, nor `crew/CLAUDE_BATCH.md` (becomes live
  data from the first real batch, never in the whitelist even if shipped as a
  skeleton at the start).
- Never modifies an existing `crew/CLAUDE_CONTEXT/TESTS_POLICY.md` (created once,
  on confirmation, if missing).
- Never modifies an existing `crew/CLAUDE_CONTEXT/CREW_CONFIG.md` (created once,
  disabled by default, if missing).
- Never overwrites a `conflict` file without explicit confirmation — prefers
  leaving a stale file over losing a user customization.
- Never silently bumps the version on a partial apply without flagging it in the
  report.
- Does not try to sync skills/agents/hooks on a plugin-mode project — redirects
  to `/plugin update crew-mates`.
- Never removes a duplicate local hook without `--remove-double-hook` confirmed
  by the user.

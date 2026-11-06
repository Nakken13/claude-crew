---
name: crew-init
description: Bootstraps the crew scaffold (CLAUDE.md, AGENTS.md, crew/…) on a new or existing project — copies, detects the stack, resolves placeholders. Also triggers on — "/crew-init", "initialise le scaffold crew", "initialize the crew scaffold".
---

This skill runs the bootstrap already described in prose in the scaffold's
`README.md` (`${CLAUDE_PLUGIN_ROOT}/template/`) — it does not replace that
document, it saves running the steps by hand and leaving a placeholder
unresolved by oversight.

## Current-state detection

1. The project already has `CLAUDE.md` + `crew/` filled in (no `<...>` left) →
   do nothing, tell the user the scaffold is already initialized and suggest
   `/crew-status` instead, or `/crew-update` if a newer scaffold version is
   available.
2. The project has `CLAUDE.md` + `crew/` with unresolved `<...>` placeholders →
   resume directly at "Placeholder resolution" below (no need to copy the files
   again).
3. Neither → full bootstrap, steps below from the start.

## Steps

0. **Check the plugin installation**: if `${CLAUDE_PLUGIN_ROOT}` is not defined or
   does not resolve to an existing directory, this skill is running outside a
   plugin context — stop immediately and tell the user to install the plugin
   first (`/plugin marketplace add Nakken13/claude-crew` then
   `/plugin install crew-mates@crew-mates`) before rerunning `/crew-init`. Never
   attempt a partial copy in this case.
1. **Copy** to the project root (without overwriting a file already present and
   already filled in), from `${CLAUDE_PLUGIN_ROOT}/template/`: `CLAUDE.md`,
   `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`,
   `check_placeholders.py`, the entire `crew/` folder (empty structure:
   `README.md` + `INDEX.md` per subfolder, no task file).
   **Do not copy** the skills, the agents, or the hook scripts — they run
   directly from the installed plugin (`${CLAUDE_PLUGIN_ROOT}`),
   `/crew-new-task`, `/crew-close-task`, `/crew-status`, `/crew-start` are
   already available with nothing to copy. Touch nothing in
   `.claude/settings.json` for the crew hooks — they are provided by the plugin
   (`hooks/hooks.json`), not by a local entry.
   **Check/install the dependencies of the skills routed in `CLAUDE.md`** —
   `claude plugin list` does not list them all, some are silently missing unless
   checked explicitly:
   - Official plugins (`claude plugin list | grep -E
     "superpowers|security-guidance|playwright|claude-md-management|frontend-design"`):
     for each missing one, `claude plugin marketplace add
     anthropics/claude-plugins-official` (idempotent if already added) then
     `claude plugin install <name>@claude-plugins-official`.
   - `taste-skill` (skill `design-taste-frontend`) — only if the project has a
     front-end stack (detected in the next step): `claude plugin list | grep
     taste-skill`; otherwise `claude plugin marketplace add
     https://github.com/Leonxlnx/taste-skill` then `claude plugin install
     taste-skill@taste-skill`.
   - `graphify` CLI (needed by `graphify init/update/query`, see § graphify of
     `CLAUDE.md`) — check `graphify` is on the PATH; otherwise `pipx install
     graphifyy` (the real pip package name, not `graphify`).
   - `impeccable` and `ui-ux-pro-max` (skills, not plugins — used by the design
     routing) — check `~/.claude/skills/impeccable` and
     `~/.claude/skills/ui-ux-pro-max`; otherwise `git clone
     https://github.com/pbakaus/impeccable.git ~/.claude/skills/impeccable` and
     `git clone https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git
     ~/.claude/skills/ui-ux-pro-max`.
   - `motion-design-rn`, `accessibility-motion`, `haptics`, `sound-design-ui`
     (only if the project has a React Native/mobile stack) — source not
     identified to date. Check `~/.claude/skills/<name>`; if missing, warn the
     user ("skill not found, source unknown — provide it or remove the RN/mobile
     line from the routing") rather than inventing an installation.
2. **Detect the real stack**: read the manifests present (`package.json`,
   `requirements.txt`/`pyproject.toml`, `go.mod`, `Cargo.toml`, etc.) — never an
   unverified assumption.
3. **Ask via `AskUserQuestion`** what cannot be deduced from the code:
   - Project name, if not already obvious from a manifest.
   - Product vision / target user / scope (`PRODUCT.md`) — option "internal
     tool, not relevant" → reduce the file to one line or delete it.
   - Commit/branch/PR convention (`CONTRIBUTING.md`) — option "no imposed
     convention" → say so explicitly rather than leave a placeholder.
   - Secrets/auth model (`SECURITY.md`) — option "no auth/sensitive data" →
     delete the file.
4. **Placeholder resolution**: replace every `<NOM_PROJET>` and `<...>` in
   `CLAUDE.md`/`AGENTS.md`/`PRODUCT.md`/`CONTRIBUTING.md`/`SECURITY.md` with the
   answers obtained + the detected stack. Repo map and verified commands: only
   commands actually run successfully during this bootstrap, never an untested
   command.
4bis. **Test policy (no extra question)**: the copied `crew/` already contains
   `crew/CLAUDE_CONTEXT/TESTS_POLICY.md`. From the project description (step 3)
   and the code (step 2), fill in the level (`light` by default; `none` only if
   the project is manifestly low-stakes; never `full`) and the risky zones in the
   project's own words. Vague description → `light` with no zones. Do not
   overwrite an already customized file.
5. **Adapt the skills routing**: in the "Skill routing" (skills routing)
   section of `CLAUDE.md`, remove the lines that do not apply to the detected
   stack (e.g. React Native/mobile lines if no RN, `dataviz` if no
   dashboard/chart).
6. If the repo is larger than a few files: run `graphify init .`.
7. Run `python check_placeholders.py` at the root. If placeholders remain,
   resolve them and rerun until exit 0.
8. Ask the user whether to keep `check_placeholders.py` as a pre-commit check or
   delete it (it is a bootstrap tool, not meant to stay by default once the
   scaffold is filled in).
9. **Report**: files created/filled, decisions taken (deleted files such as
   `PRODUCT.md`, lines removed from the skills routing), final status of
   `check_placeholders.py`, and the **deduced test policy** (level + risky zones,
   editable in `TESTS_POLICY.md`).

## What this skill does not do

- Never rewrites an already filled-in `CLAUDE.md`/`AGENTS.md` unless the user
  explicitly asked.
- Does not guess the stack or the commands — reads the manifests / actually runs
  them, never assumes.
- Does not run `graphify init` on a trivial repo (a few files) — not useful at
  that scale.

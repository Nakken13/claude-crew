# claude-crew as a Claude Code marketplace plugin

## Goal

Publish `claude-crew` as an installable Claude Code **plugin**, distributed
via a **marketplace** hosted in this same repo, so anyone can run:

```
/plugin marketplace add Nakken13/claude-crew
/plugin install claude-crew@claude-crew
/crew-init
```

on any project and get the full crew task-lifecycle system, without cloning
this repo or hand-copying files from a local machine.

## Non-goals

- Not building a separate marketplace repo (out of scope; revisit if a
  second plugin is ever published).
- Not submitting to a third-party/community marketplace.
- Not changing the crew task-lifecycle model itself (folders, batching,
  hooks' behavior) — only how it's packaged and installed.
- Not designing the "update an already-bootstrapped project" flow in full —
  that's the existing backlog task
  `crew/TODO/mecanisme-mise-a-jour-scaffold-multi-projets.md`. This plugin
  packaging is what *enables* a clean version of that flow later (plugin
  update = engine update for every project that installed it), but the
  update mechanism itself stays a separate task.

## Architecture

Plugin-native model: skills, agents, and hooks run directly from the
installed plugin via `${CLAUDE_PLUGIN_ROOT}`. Nothing engine-related gets
copied into the target project. `crew-init` only writes the minimal
per-project data: filled-in root docs + empty `crew/` task folders.

```
claude-crew (repo root = marketplace source)
├── .claude-plugin/
│   ├── plugin.json          # manifest: name, version, description, license
│   └── marketplace.json     # lists this plugin as the repo's marketplace entry
├── skills/
│   ├── crew-init/SKILL.md
│   ├── crew-new-task/SKILL.md
│   ├── crew-close-task/SKILL.md
│   ├── crew-status/SKILL.md
│   └── crew-start/SKILL.md
├── agents/
│   ├── manager.md
│   ├── ceo.md
│   ├── architect.md
│   └── comms.md
├── hooks/
│   └── hooks.json            # Stop, SessionEnd -> crew_hook.py; PostToolUse(Write) -> spec_to_task_hook.py
├── scripts/
│   ├── crew_hook.py
│   └── spec_to_task_hook.py
├── template/                 # neutral scaffold, source of truth (copied from
│   │                          # ~/.claude/templates/project-scaffold/, this repo
│   │                          # now owns it, not the local machine)
│   ├── CLAUDE.md
│   ├── AGENTS.md
│   ├── PRODUCT.md
│   ├── CONTRIBUTING.md
│   ├── SECURITY.md
│   ├── check_placeholders.py
│   └── crew/                 # README.md + empty INDEX.md per folder, no task files
│       ├── PROBLEMS/ TODO/ CURRENT_TASKS/ ICEBOX/
│       └── TESTS/IA/ TESTS/DEV/ CLAUDE_CONTEXT/TESTS_DONE/
└── (repo's own root CLAUDE.md, crew/, .claude/ stay exactly as-is —
     this project's own dogfood instance, untouched by this work)
```

### What moves where

| Today (this repo, dogfooding) | Plugin equivalent |
|---|---|
| `.claude/skills/crew-*/SKILL.md` | `skills/crew-*/SKILL.md` (same content, plugin-root convention) |
| `.claude/agents/*.md` | `agents/*.md` |
| `crew/crew_hook.py`, `crew/spec_to_task_hook.py` | `scripts/*.py`, invoked via `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}/scripts/...` |
| `.claude/settings.json` hook wiring (crew-related entries only) | `hooks/hooks.json` |
| `~/.claude/templates/project-scaffold/*` | `template/*` (repo becomes source of truth; local machine copy becomes stale/removable) |

**Explicitly excluded from the plugin's `hooks.json`**: the graphify
PreToolUse nudges present in this repo's own `.claude/settings.json`. Those
are this repo's own dogfood config (this repo happens to use graphify on
itself), not part of the crew product surface advertised in the README's
"what's in the box" table. They stay local to this repo, not shipped.

## Components

- **`plugin.json`** — standard Claude Code plugin manifest: `name:
  "claude-crew"`, `description`, `version` (start `0.1.0` — see Versioning),
  `author`, `license: "MIT"`, `homepage` pointing at the GitHub repo.
- **`marketplace.json`** — single-plugin marketplace listing, `name:
  "claude-crew"`, source `.` (this repo), pointing at the plugin above.
- **`hooks/hooks.json`** — declares exactly the two advertised hooks:
  - `Stop` and `SessionEnd` → `${CLAUDE_PLUGIN_ROOT}/scripts/crew_hook.py`
  - `PostToolUse` (matcher `Write`) → `${CLAUDE_PLUGIN_ROOT}/scripts/spec_to_task_hook.py`

  Scripts keep reading/writing `$CLAUDE_PROJECT_DIR/crew/...` exactly as
  today — that variable already resolves to the *target* project, so no
  script logic changes are needed for this part.
- **`skills/crew-init/SKILL.md`** — rewritten copy step: source becomes
  `${CLAUDE_PLUGIN_ROOT}/template/` instead of
  `~/.claude/templates/project-scaffold/`. Copies only: `CLAUDE.md`,
  `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `check_placeholders.py`, empty `crew/` folder tree. Does **not** copy
  `.claude/skills/crew-*`, `.claude/agents/*`, or the two hook scripts —
  those now come from the installed plugin, not a per-project copy. Detects
  `${CLAUDE_PLUGIN_ROOT}` being unset (plugin not installed in this session)
  and tells the user to install the plugin first instead of failing
  silently or half-copying.
- **`skills/crew-new-task`, `crew-close-task`, `crew-status`,
  `crew-start`** — unchanged logic, moved as-is to `skills/`.
- **`agents/*.md`** — unchanged, moved as-is to `agents/`.

## Data flow

Unaffected for the day-to-day crew lifecycle — task files still move
between `crew/*` folders in the *target* project exactly as documented in
that project's own `CLAUDE.md`. The only new flow is install-time:

```
/plugin marketplace add Nakken13/claude-crew
  -> Claude Code reads .claude-plugin/marketplace.json from this repo
/plugin install claude-crew@claude-crew
  -> plugin files (skills/, agents/, hooks/, scripts/, template/) become
     available in the installing session via ${CLAUDE_PLUGIN_ROOT}
/crew-init (in target project)
  -> reads template/ from the plugin, writes root docs + empty crew/ tree
     into the target project, resolves placeholders via AskUserQuestion
     as today
```

## Error handling

- `crew-init` run without the plugin installed: detect `${CLAUDE_PLUGIN_ROOT}`
  unset/unresolvable, tell the user to `/plugin install claude-crew@claude-crew`
  first, do not partially copy files.
- `crew-init` run on a project that already has a filled `CLAUDE.md`/`crew/`:
  unchanged existing behavior (refuse to overwrite, point to `/crew-status`).
- Hook scripts: unchanged existing failure handling (non-blocking stderr
  warnings), no new failure modes introduced by the path change since
  `$CLAUDE_PROJECT_DIR` resolution is untouched.

## Versioning

Start `plugin.json` at `0.1.0`. No `VERSION`/`CHANGELOG.md` machinery yet —
that's the separate backlog task
`mecanisme-mise-a-jour-scaffold-multi-projets.md`, which this plugin
packaging unblocks but does not implement.

## Testing

🤖 (IA, scriptable):
- `python check_placeholders.py` exits 0 after `crew-init` fills the copied
  template in a scratch directory.
- `hooks/hooks.json` schema is well-formed JSON and references existing
  script paths.
- `crew-init` in a scratch dir with `${CLAUDE_PLUGIN_ROOT}` unset produces
  the "install the plugin first" message rather than a partial copy or crash.
- Diff `template/` against a fresh export from
  `~/.claude/templates/project-scaffold/` to confirm no drift was introduced
  while restructuring.

🖱️ (DEV, manual):
- End-to-end from a clean Claude Code profile: `/plugin marketplace add
  Nakken13/claude-crew`, `/plugin install claude-crew@claude-crew`,
  `/crew-init` on a throwaway project, confirm skills/agents/hooks all
  resolve and fire correctly from the plugin install (not a local copy).
- Confirm `crew-new-task`, `crew-close-task`, `crew-status`, `crew-start`
  all still trigger correctly by their documented `/crew-*` phrasing once
  running from the plugin instead of `.claude/skills/`.

## Out of scope / follow-ups

- Scrubbing the already-public `nahel` Windows path in
  `crew/CLAUDE_CONTEXT/TESTS_DONE/rename-organized-to-crew.md` (would need
  history rewrite + force-push; left as-is per user decision during this
  session's pre-flight check).
- Renaming the GitHub remote itself from `organized` to `claude-crew`
  (currently `origin` still points at `Nakken13/organized.git`) — separate,
  optional cleanup, not required for the plugin/marketplace to work.
- The full scaffold-update mechanism for already-bootstrapped projects
  (`crew/TODO/mecanisme-mise-a-jour-scaffold-multi-projets.md`).

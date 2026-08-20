# claude-crew Marketplace Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package `claude-crew` as an installable Claude Code plugin, distributed via a marketplace hosted in this same repo (`/plugin marketplace add Nakken13/claude-crew` → `/plugin install claude-crew@claude-crew`).

**Architecture:** New top-level plugin directories (`.claude-plugin/`, `skills/`, `agents/`, `hooks/`, `scripts/`, `template/`) hold the plugin's distributable artifacts, built by **copying** (never moving) from this repo's existing `.claude/skills/crew-*`, `.claude/agents/`, `crew/crew_hook.py`, `crew/spec_to_task_hook.py`, and `~/.claude/templates/project-scaffold/`. This repo's own `.claude/`, `crew/`, and root docs stay untouched and keep dogfooding exactly as today — per the approved spec's explicit non-goal, and because this repo's own session hooks run live against those files right now; moving/deleting them mid-plan would break this very session. De-duplicating (self-installing the plugin locally and retiring the local copies) is an explicit follow-up, not part of this plan.

**Tech Stack:** Stdlib-only Python (matches repo's "Dependencies: none" badge), plain JSON manifests, Markdown skill/agent files. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-20-marketplace-plugin-design.md`

## Global Constraints

- Never modify `.claude/skills/crew-*`, `.claude/agents/*`, `crew/crew_hook.py`, `crew/spec_to_task_hook.py`, `.claude/settings.json`, or this repo's own root `CLAUDE.md`/`AGENTS.md`/`PRODUCT.md`/`CONTRIBUTING.md`/`SECURITY.md` — copy from them, never edit or delete them, in this plan.
- Plugin's `hooks/hooks.json` ships **only** the two advertised hooks (`crew_hook.py` on Stop+SessionEnd, `spec_to_task_hook.py` on PostToolUse/Write). Never include the graphify PreToolUse nudges from this repo's local `.claude/settings.json` — those are this repo's own dogfood config, not product surface.
- All new scripts are stdlib-only Python 3 (no pip dependencies), matching the rest of the repo.
- Every plugin JSON manifest must be valid JSON and — before being treated as final — checked against the real `claude plugin`/`claude plugin marketplace` CLI help output, never against assumed/remembered schema alone (a repo-wide rule already enforced in `crew-init`'s own "never invent an untested command" principle).
- Use `$HOME/.claude/templates/project-scaffold` (not a hardcoded Windows path) when referencing the global template source, for portability.

---

### Task 1: Plugin + marketplace manifests

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `scripts/dev/verify_plugin_package.py`
- Test: `scripts/dev/verify_plugin_package.py` (self-contained script, doubles as its own test runner — no separate test file; this repo has no pytest infra and stays stdlib-only)

**Interfaces:**
- Produces: `scripts/dev/verify_plugin_package.py` exposes `check_manifests(repo_root: Path) -> list[str]` (returns list of problem strings, empty = pass) and a `main()` that runs all registered `check_*` functions, prints results, exits 1 if any problems. Later tasks import/extend this same file by adding more `check_*` functions and registering them in `main()`'s `CHECKS` list — this is the shared convention every later task's "Interfaces: Consumes" block refers to.

- [ ] **Step 1: Confirm real plugin/marketplace manifest schema**

Run: `claude plugin --help` and `claude plugin marketplace --help` (and `claude plugin validate --help` if it exists).

Read the output. Confirm the required/optional fields for a plugin manifest (`name`, `version`, `description`, `author`, `license`, `homepage` — or whatever the real CLI documents) and for a marketplace manifest (`name`, `owner`, `plugins[]` with `name`/`source` — or whatever the real CLI documents). If the CLI exposes a `claude plugin validate` or similar command, note the exact invocation for Step 4 below. Do not proceed on memory alone — this step exists specifically to catch drift between assumed and real schema.

- [ ] **Step 2: Write the failing check**

Create `scripts/dev/verify_plugin_package.py`:

```python
#!/usr/bin/env python3
"""Structural integrity checks for the claude-crew plugin package.

Run directly: python scripts/dev/verify_plugin_package.py
Exits 0 if every check passes, 1 otherwise (with problems printed).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def check_manifests(repo_root: Path) -> list[str]:
    problems = []
    plugin_path = repo_root / ".claude-plugin" / "plugin.json"
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"

    if not plugin_path.exists():
        problems.append(f"missing {plugin_path}")
    else:
        try:
            data = json.loads(plugin_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"{plugin_path} is not valid JSON: {e}")
        else:
            for key in ("name", "version", "description", "license"):
                if not data.get(key):
                    problems.append(f"{plugin_path} missing required key: {key}")

    if not marketplace_path.exists():
        problems.append(f"missing {marketplace_path}")
    else:
        try:
            data = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"{marketplace_path} is not valid JSON: {e}")
        else:
            if not data.get("name"):
                problems.append(f"{marketplace_path} missing required key: name")
            plugins = data.get("plugins")
            if not plugins or not isinstance(plugins, list):
                problems.append(f"{marketplace_path} missing non-empty 'plugins' list")
            elif not any(p.get("name") == "claude-crew" for p in plugins):
                problems.append(f"{marketplace_path} 'plugins' list has no entry named claude-crew")

    return problems


CHECKS = [check_manifests]


def main() -> int:
    problems = []
    for check in CHECKS:
        problems.extend(check(REPO_ROOT))
    if problems:
        print(f"FAIL ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"PASS ({len(CHECKS)} check(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run it to confirm it fails**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `FAIL` — reports `missing .claude-plugin/plugin.json` and `missing .claude-plugin/marketplace.json`.

- [ ] **Step 4: Write the manifests**

Create `.claude-plugin/plugin.json` (adjust fields per Step 1's real schema findings if they differ from this draft):

```json
{
  "name": "claude-crew",
  "version": "0.1.0",
  "description": "File-based task lifecycle + multi-agent collision prevention for Claude Code.",
  "author": {
    "name": "Nakken13",
    "url": "https://github.com/Nakken13"
  },
  "license": "MIT",
  "homepage": "https://github.com/Nakken13/claude-crew"
}
```

Create `.claude-plugin/marketplace.json` (adjust per Step 1 findings if different):

```json
{
  "name": "claude-crew",
  "owner": {
    "name": "Nakken13",
    "url": "https://github.com/Nakken13"
  },
  "plugins": [
    {
      "name": "claude-crew",
      "source": ".",
      "description": "File-based task lifecycle + multi-agent collision prevention for Claude Code."
    }
  ]
}
```

If Step 1 found a `claude plugin validate` (or equivalent) command, also run it now against `.claude-plugin/` and fix any reported schema issues before moving on.

- [ ] **Step 5: Run it to confirm it passes**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `PASS (1 check(s))`

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json scripts/dev/verify_plugin_package.py
git commit -m "feat: add plugin + marketplace manifests for claude-crew"
```

---

### Task 2: `template/` — neutral scaffold, repo becomes source of truth

**Files:**
- Create: `template/CLAUDE.md`, `template/AGENTS.md`, `template/PRODUCT.md`, `template/CONTRIBUTING.md`, `template/SECURITY.md`, `template/check_placeholders.py`
- Create: `template/crew/` tree — `PROBLEMS/`, `TODO/`, `CURRENT_TASKS/`, `ICEBOX/`, `TESTS/IA/`, `TESTS/DEV/`, `CLAUDE_CONTEXT/TESTS_DONE/`, each with its `README.md` + empty `INDEX.md` only (no task files — copied straight from `$HOME/.claude/templates/project-scaffold/crew/`, which already holds README/INDEX-only placeholders, never this repo's own live task data)
- Modify: `scripts/dev/verify_plugin_package.py` — add `check_template_matches_source`

**Interfaces:**
- Consumes: `CHECKS` list and `main()` from Task 1 (unchanged).
- Produces: `check_template_matches_source(repo_root: Path) -> list[str]`, added to `CHECKS`.

- [ ] **Step 1: Write the failing check**

Edit `scripts/dev/verify_plugin_package.py` — add before `CHECKS = [check_manifests]`:

```python
import filecmp


def check_template_matches_source(repo_root: Path) -> list[str]:
    problems = []
    template_dir = repo_root / "template"
    source_dir = Path.home() / ".claude" / "templates" / "project-scaffold"

    if not template_dir.exists():
        problems.append(f"missing {template_dir}")
        return problems
    if not source_dir.exists():
        problems.append(f"source scaffold not found at {source_dir} — cannot verify drift")
        return problems

    comparison = filecmp.dircmp(source_dir, template_dir)
    only_in_source = _collect_diffs(comparison, "only_in_source")
    only_in_template = _collect_diffs(comparison, "only_in_template")
    if only_in_source:
        problems.append(f"files present in {source_dir} but missing from {template_dir}: {only_in_source}")
    if only_in_template:
        problems.append(f"files present in {template_dir} but not in source scaffold: {only_in_template}")
    if comparison.diff_files:
        problems.append(f"content differs from source scaffold: {comparison.diff_files}")
    return problems


def _collect_diffs(comparison, attr, prefix=""):
    label = "left_only" if attr == "only_in_source" else "right_only"
    found = [f"{prefix}{name}" for name in getattr(comparison, label)]
    for sub_name, sub_comparison in comparison.subdirs.items():
        found.extend(_collect_diffs(sub_comparison, attr, prefix=f"{prefix}{sub_name}/"))
    return found
```

Change `CHECKS = [check_manifests]` to:

```python
CHECKS = [check_manifests, check_template_matches_source]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `FAIL` — reports `missing <repo>/template`.

- [ ] **Step 3: Copy the scaffold**

```bash
mkdir -p template
cp -r "$HOME/.claude/templates/project-scaffold/." template/
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `PASS (2 check(s))`

If it reports a drift (e.g. `content differs`), inspect with `diff -r "$HOME/.claude/templates/project-scaffold" template` and resolve — the copy must be byte-identical to the source at this point; no edits yet.

- [ ] **Step 5: Commit**

```bash
git add template/ scripts/dev/verify_plugin_package.py
git commit -m "feat: add neutral scaffold template/, sourced from local project-scaffold"
```

---

### Task 3: Copy engine files into plugin root (`skills/`, `agents/`, `scripts/`)

**Files:**
- Create: `skills/crew-close-task/SKILL.md`, `skills/crew-init/SKILL.md`, `skills/crew-new-task/SKILL.md`, `skills/crew-start/SKILL.md`, `skills/crew-status/SKILL.md`
- Create: `agents/architect.md`, `agents/ceo.md`, `agents/comms.md`, `agents/manager.md`
- Create: `scripts/crew_hook.py`, `scripts/spec_to_task_hook.py`
- Modify: `scripts/dev/verify_plugin_package.py` — add `check_engine_files_copied`

**Interfaces:**
- Consumes: `CHECKS`, `main()` from Task 1/2 (unchanged).
- Produces: `check_engine_files_copied(repo_root: Path) -> list[str]`, added to `CHECKS`. Later tasks (5) will modify `skills/crew-init/SKILL.md` in place — this task's job is only to get an exact copy in place first.

- [ ] **Step 1: Write the failing check**

Edit `scripts/dev/verify_plugin_package.py` — add:

```python
ENGINE_FILE_PAIRS = [
    (".claude/skills/crew-close-task/SKILL.md", "skills/crew-close-task/SKILL.md"),
    (".claude/skills/crew-init/SKILL.md", "skills/crew-init/SKILL.md"),
    (".claude/skills/crew-new-task/SKILL.md", "skills/crew-new-task/SKILL.md"),
    (".claude/skills/crew-start/SKILL.md", "skills/crew-start/SKILL.md"),
    (".claude/skills/crew-status/SKILL.md", "skills/crew-status/SKILL.md"),
    (".claude/agents/architect.md", "agents/architect.md"),
    (".claude/agents/ceo.md", "agents/ceo.md"),
    (".claude/agents/comms.md", "agents/comms.md"),
    (".claude/agents/manager.md", "agents/manager.md"),
    ("crew/crew_hook.py", "scripts/crew_hook.py"),
    ("crew/spec_to_task_hook.py", "scripts/spec_to_task_hook.py"),
]


def check_engine_files_copied(repo_root: Path) -> list[str]:
    problems = []
    for _source_rel, target_rel in ENGINE_FILE_PAIRS:
        target = repo_root / target_rel
        if not target.exists():
            problems.append(f"missing {target}")
    return problems
```

Change `CHECKS = [check_manifests, check_template_matches_source]` to:

```python
CHECKS = [check_manifests, check_template_matches_source, check_engine_files_copied]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `FAIL` — 11 `missing ...` entries, one per target in `ENGINE_FILE_PAIRS`.

- [ ] **Step 3: Copy the files**

```bash
mkdir -p skills agents scripts
for pair in \
  ".claude/skills/crew-close-task/SKILL.md:skills/crew-close-task/SKILL.md" \
  ".claude/skills/crew-init/SKILL.md:skills/crew-init/SKILL.md" \
  ".claude/skills/crew-new-task/SKILL.md:skills/crew-new-task/SKILL.md" \
  ".claude/skills/crew-start/SKILL.md:skills/crew-start/SKILL.md" \
  ".claude/skills/crew-status/SKILL.md:skills/crew-status/SKILL.md" \
  ".claude/agents/architect.md:agents/architect.md" \
  ".claude/agents/ceo.md:agents/ceo.md" \
  ".claude/agents/comms.md:agents/comms.md" \
  ".claude/agents/manager.md:agents/manager.md" \
  "crew/crew_hook.py:scripts/crew_hook.py" \
  "crew/spec_to_task_hook.py:scripts/spec_to_task_hook.py" ; do
  src="${pair%%:*}"; dst="${pair##*:}"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
done
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `PASS (3 check(s))`

- [ ] **Step 5: Commit**

```bash
git add skills/ agents/ scripts/crew_hook.py scripts/spec_to_task_hook.py scripts/dev/verify_plugin_package.py
git commit -m "feat: copy crew skills/agents/hook scripts into plugin root"
```

---

### Task 4: `hooks/hooks.json`

**Files:**
- Create: `hooks/hooks.json`
- Modify: `scripts/dev/verify_plugin_package.py` — add `check_hooks_json`

**Interfaces:**
- Consumes: `scripts/crew_hook.py`, `scripts/spec_to_task_hook.py` from Task 3 (must already exist).
- Produces: `check_hooks_json(repo_root: Path) -> list[str]`, added to `CHECKS`.

- [ ] **Step 1: Write the failing check**

Edit `scripts/dev/verify_plugin_package.py` — add:

```python
def check_hooks_json(repo_root: Path) -> list[str]:
    problems = []
    hooks_path = repo_root / "hooks" / "hooks.json"
    if not hooks_path.exists():
        problems.append(f"missing {hooks_path}")
        return problems

    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        problems.append(f"{hooks_path} is not valid JSON: {e}")
        return problems

    events = data.get("hooks", {})
    for event_name in ("Stop", "SessionEnd", "PostToolUse"):
        if event_name not in events:
            problems.append(f"{hooks_path} missing event: {event_name}")

    text = hooks_path.read_text(encoding="utf-8")
    for script_rel in ("scripts/crew_hook.py", "scripts/spec_to_task_hook.py"):
        if script_rel not in text:
            problems.append(f"{hooks_path} does not reference {script_rel}")
        if not (repo_root / script_rel).exists():
            problems.append(f"{hooks_path} references {script_rel} but it does not exist")

    if "graphify" in text.lower():
        problems.append(f"{hooks_path} must not reference graphify (dogfood-only, not product surface)")

    return problems


CHECKS = [check_manifests, check_template_matches_source, check_engine_files_copied, check_hooks_json]
```

(replacing the previous `CHECKS = [...]` line)

- [ ] **Step 2: Run it to confirm it fails**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `FAIL` — reports `missing hooks/hooks.json`.

- [ ] **Step 3: Write `hooks/hooks.json`**

Mirror this repo's own `.claude/settings.json` Stop/SessionEnd/PostToolUse blocks (same Python-resolution idiom), swapping `$CLAUDE_PROJECT_DIR/crew/*.py` for `${CLAUDE_PLUGIN_ROOT}/scripts/*.py`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python); \"$PY\" \"${CLAUDE_PLUGIN_ROOT}/scripts/spec_to_task_hook.py\"",
            "statusMessage": "Spec superpowers -> tache CURRENT_TASKS",
            "timeout": 15
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python); \"$PY\" \"${CLAUDE_PLUGIN_ROOT}/scripts/crew_hook.py\"",
            "statusMessage": "Sync crew (index / journal / invariants / verrous batch)",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python); \"$PY\" \"${CLAUDE_PLUGIN_ROOT}/scripts/crew_hook.py\"",
            "statusMessage": "Libère les verrous batch de la session",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `PASS (4 check(s))`

- [ ] **Step 5: Commit**

```bash
git add hooks/hooks.json scripts/dev/verify_plugin_package.py
git commit -m "feat: declare plugin hooks (crew_hook.py, spec_to_task_hook.py)"
```

---

### Task 5: Rewrite the plugin's `skills/crew-init/SKILL.md` for plugin-native install

**Files:**
- Modify: `skills/crew-init/SKILL.md` (the Task-3 copy only — never `.claude/skills/crew-init/SKILL.md`, per Global Constraints)
- Modify: `scripts/dev/verify_plugin_package.py` — add `check_crew_init_is_plugin_native`

**Interfaces:**
- Consumes: `template/` from Task 2 (the new copy source `crew-init` must reference).
- Produces: `check_crew_init_is_plugin_native(repo_root: Path) -> list[str]`, added to `CHECKS`.

- [ ] **Step 1: Write the failing check**

Edit `scripts/dev/verify_plugin_package.py` — add:

```python
def check_crew_init_is_plugin_native(repo_root: Path) -> list[str]:
    problems = []
    skill_path = repo_root / "skills" / "crew-init" / "SKILL.md"
    if not skill_path.exists():
        problems.append(f"missing {skill_path}")
        return problems

    text = skill_path.read_text(encoding="utf-8")
    if "${CLAUDE_PLUGIN_ROOT}/template" not in text:
        problems.append(f"{skill_path} does not reference \\${{CLAUDE_PLUGIN_ROOT}}/template")
    if "~/.claude/templates/project-scaffold" in text:
        problems.append(f"{skill_path} still references the local-machine template path")
    if ".claude/skills/crew-*" in text or ".claude/agents/" in text:
        problems.append(f"{skill_path} still instructs copying skills/agents into the target project")
    if "CLAUDE_PLUGIN_ROOT" not in text or "install" not in text.lower():
        problems.append(f"{skill_path} has no guard for a missing/unset CLAUDE_PLUGIN_ROOT")
    return problems


CHECKS = [
    check_manifests,
    check_template_matches_source,
    check_engine_files_copied,
    check_hooks_json,
    check_crew_init_is_plugin_native,
]
```

(replacing the previous `CHECKS = [...]` line)

- [ ] **Step 2: Run it to confirm it fails**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `FAIL` — `skills/crew-init/SKILL.md` still has the old `~/.claude/templates/project-scaffold` reference and the `.claude/skills/crew-*`/`.claude/agents/` copy instructions, and no `CLAUDE_PLUGIN_ROOT` guard.

- [ ] **Step 3: Edit `skills/crew-init/SKILL.md`**

Replace the "Étapes" step 1 block (originally lines 21-58 in the source `.claude/skills/crew-init/SKILL.md`) with:

```markdown
## Étapes

0. **Vérifier l'installation du plugin** : si `${CLAUDE_PLUGIN_ROOT}` n'est pas
   défini ou ne résout vers aucun répertoire existant, ce skill tourne hors
   contexte plugin — arrêter immédiatement et dire à l'utilisateur d'installer
   d'abord le plugin (`/plugin marketplace add Nakken13/claude-crew` puis
   `/plugin install claude-crew@claude-crew`) avant de relancer `/crew-init`.
   Ne jamais tenter une copie partielle dans ce cas.
1. **Copier** à la racine du projet (sans écraser un fichier déjà présent et
   déjà rempli), depuis `${CLAUDE_PLUGIN_ROOT}/template/` : `CLAUDE.md`,
   `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`,
   `check_placeholders.py`, le dossier `crew/` entier (structure vide :
   `README.md` + `INDEX.md` par sous-dossier, aucun fichier de tâche).
   **Ne pas copier** les skills, les agents, ni les scripts de hooks — ils
   tournent directement depuis le plugin installé (`${CLAUDE_PLUGIN_ROOT}`),
   `/crew-new-task`, `/crew-close-task`, `/crew-status`, `/crew-start` sont
   déjà disponibles sans rien copier. Ne rien toucher à `.claude/settings.json`
   pour les hooks crew — ils sont fournis par le plugin (`hooks/hooks.json`),
   pas par une entrée locale.
   **Vérifier/installer les dépendances des skills routés dans `CLAUDE.md`** —
   `claude plugin list` ne les liste pas tous, certains manquent silencieusement
   si on ne les checke pas explicitement :
   - Plugins officiels (`claude plugin list | grep -E
     "superpowers|security-guidance|playwright|claude-md-management|frontend-design"`) :
     pour chaque manquant, `claude plugin marketplace add
     anthropics/claude-plugins-official` (idempotent si déjà ajoutée) puis
     `claude plugin install <nom>@claude-plugins-official`.
   - `taste-skill` (skill `design-taste-frontend`) — uniquement si le projet a
     une stack front (détectée à l'étape suivante) : `claude plugin list | grep
     taste-skill` ; sinon `claude plugin marketplace add
     https://github.com/Leonxlnx/taste-skill` puis `claude plugin install
     taste-skill@taste-skill`.
   - `graphify` CLI (nécessaire à `graphify init/update/query`, cf. § graphify
     de `CLAUDE.md`) — vérifier `graphify` sur le PATH ; sinon `pipx install
     graphifyy` (nom du package pip réel, pas `graphify`).
   - `impeccable` et `ui-ux-pro-max` (skills, pas des plugins — utilisés par le
     routage design) — vérifier `~/.claude/skills/impeccable` et
     `~/.claude/skills/ui-ux-pro-max` ; sinon `git clone
     https://github.com/pbakaus/impeccable.git ~/.claude/skills/impeccable` et
     `git clone https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git
     ~/.claude/skills/ui-ux-pro-max`.
   - `motion-design-rn`, `accessibility-motion`, `haptics`, `sound-design-ui`
     (uniquement si le projet a une stack React Native/mobile) — source non
     identifiée à ce jour. Vérifier `~/.claude/skills/<nom>` ; si absent,
     avertir l'utilisateur ("skill non trouvé, source inconnue — le fournir ou
     retirer la ligne RN/mobile du routage") plutôt que d'inventer une
     installation.
```

Leave steps 2-9 (stack detection, `AskUserQuestion`, placeholder resolution, skill-routing adaptation, `graphify init`, `check_placeholders.py`, report) unchanged — they don't reference the copy source or the skills/agents/hooks location.

- [ ] **Step 4: Run it to confirm it passes**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `PASS (5 check(s))`

- [ ] **Step 5: Commit**

```bash
git add skills/crew-init/SKILL.md scripts/dev/verify_plugin_package.py
git commit -m "feat: make plugin's crew-init copy from template/, plugin-native"
```

---

### Task 6: README install section + full suite

**Files:**
- Modify: `README.md`
- Modify: `scripts/dev/verify_plugin_package.py` — add `check_readme_has_marketplace_install`

**Interfaces:**
- Consumes: nothing new — final integration point, reads the finished `CHECKS` list.
- Produces: `check_readme_has_marketplace_install(repo_root: Path) -> list[str]`, added to `CHECKS`. No further tasks depend on this.

- [ ] **Step 1: Write the failing check**

Edit `scripts/dev/verify_plugin_package.py` — add:

```python
def check_readme_has_marketplace_install(repo_root: Path) -> list[str]:
    problems = []
    readme = repo_root / "README.md"
    text = readme.read_text(encoding="utf-8")
    if "/plugin marketplace add Nakken13/claude-crew" not in text:
        problems.append(f"{readme} missing the /plugin marketplace add command")
    if "/plugin install claude-crew@claude-crew" not in text:
        problems.append(f"{readme} missing the /plugin install command")
    return problems


CHECKS = [
    check_manifests,
    check_template_matches_source,
    check_engine_files_copied,
    check_hooks_json,
    check_crew_init_is_plugin_native,
    check_readme_has_marketplace_install,
]
```

(replacing the previous `CHECKS = [...]` line)

- [ ] **Step 2: Run it to confirm it fails**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `FAIL` — both README checks fail.

- [ ] **Step 3: Add the install section to README.md**

Read the current "Quick start" section first (`grep -n "Quick start" README.md`) to place this immediately after it, matching the existing heading style/emoji convention used elsewhere in the file. Add:

```markdown
### 🔌 Install via marketplace (recommended)

```
/plugin marketplace add Nakken13/claude-crew
/plugin install claude-crew@claude-crew
/crew-init
```

No cloning, no manual file copying — skills, agents, and hooks run straight
from the installed plugin. `/crew-init` still asks the same bootstrap
questions (product vision, commit conventions, secrets model) and writes the
same project files as the manual flow below.
```

- [ ] **Step 4: Run it to confirm it passes**

Run: `python scripts/dev/verify_plugin_package.py`
Expected: `PASS (6 check(s))`

- [ ] **Step 5: Commit**

```bash
git add README.md scripts/dev/verify_plugin_package.py
git commit -m "docs: add marketplace install instructions to README"
```

---

## After this plan

- `crew/TESTS/DEV/marketplace-plugin.md` (🖱️): end-to-end `/plugin marketplace add Nakken13/claude-crew` → `/plugin install claude-crew@claude-crew` → `/crew-init` on a throwaway project, from a clean Claude Code profile — cannot be scripted in this plan, run manually once published.
- `crew/TESTS/IA/marketplace-plugin.md` (🤖): re-run `python scripts/dev/verify_plugin_package.py` as the automated regression check; also have an agent actually run `/crew-init` end-to-end against a scratch directory with `CLAUDE_PLUGIN_ROOT` pointed at this repo, then run `python check_placeholders.py` in that scratch dir after resolving placeholders, expecting exit 0.
- Follow-up (separate task, not this plan): self-install the plugin locally (`/plugin marketplace add .` from this repo) and retire the now-duplicated `.claude/skills/crew-*`, `.claude/agents/`, `crew/crew_hook.py`, `crew/spec_to_task_hook.py`, and the crew-related entries in `.claude/settings.json`, so this repo dogfoods itself through the same plugin path everyone else uses.
- `/crew-close-task` on `crew/CURRENT_TASKS/marketplace-plugin.md` once the above testing is done — historize in `HISTORIQUE.md`, file the two test checklists, remove the task file.

# -*- coding: utf-8 -*-
"""Update engine for the crew scaffold on an already-bootstrapped project
(task mecanisme-mise-a-jour-scaffold-multi-projets).

For each "engine" file in an allowlist, compares the target project's local
content with the scaffold source, relying on a hash recorded at the last
write (crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json) so a user customization is
never silently overwritten.

Never writes to user data folders (crew/TODO, crew/CURRENT_TASKS,
crew/PROBLEMS, crew/ICEBOX, crew/TESTS, crew/CLAUDE_CONTEXT/HISTORY.md (or HISTORIQUE.md),
...): only the explicit allowlist passed by the caller is ever touched.

CLI usage (dry-run by default, writes nothing without --apply):
    python crew_update.py --project <dir> --source <dir> [--apply]
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

USER_SETTINGS_PATH = pathlib.Path.home() / ".claude" / "settings.json"
PROJECT_SETTINGS_FILES = ("settings.json", "settings.local.json")
PLUGIN_NAME = "crew-mates"
LEGACY_PLUGIN_NAME = "claude-crew"  # name before the rename: projects not migrated
LOCAL_HOOK_RE = re.compile(r"(^|[\s\"'/\\=])crew[/\\]crew_hook\.py")

SCAFFOLD_VERSION_REL = pathlib.Path("crew") / "CLAUDE_CONTEXT" / "SCAFFOLD_VERSION.json"

# Engine files common to every project bootstrapped via crew-init, whatever
# the install mode (plugin or manual clone).
ENGINE_FILES_COMMON = [
    "CLAUDE.md",
    "AGENTS.md",
    "PRODUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "check_placeholders.py",
    "crew/dashboard.bat",
    "crew/CLAUDE_CONTEXT/LIFECYCLE.md",
]

# Extra engine files, only for projects bootstrapped before the plugin
# repackaging (Option C / manual clone): skills, agents and hooks copied
# locally rather than served from ${CLAUDE_PLUGIN_ROOT}.
ENGINE_FILES_LEGACY = [
    "crew/crew_hook.py",
    "crew/spec_to_task_hook.py",
    ".claude/skills/crew-init/SKILL.md",
    ".claude/skills/crew-new-task/SKILL.md",
    ".claude/skills/crew-close-task/SKILL.md",
    ".claude/skills/crew-status/SKILL.md",
    ".claude/skills/crew-start/SKILL.md",
    ".claude/skills/crew-collab/SKILL.md",
    # Preloaded by the designer persona: without it a legacy project would
    # receive a designer.md pointing at a skill it does not have.
    ".claude/skills/ux-intuitive/SKILL.md",
    ".claude/skills/ux-intuitive/references/platform-specs.md",
    ".claude/skills/ux-intuitive/references/expert-patterns.md",
    ".claude/skills/ux-intuitive/references/emotional-design.md",
]
# Skill folders the scaffold copied into pre-plugin projects (derived, never listed twice).
LEGACY_SKILL_NAMES = sorted({rel.split("/")[2] for rel in ENGINE_FILES_LEGACY if rel.startswith(".claude/skills/")})

# Migrate mode (local copies + plugin): the local hook scripts stay synced — they are not
# loaded as skills/agents, and a plugin + local *hook* pair is handled by detect_double_hook().
MIGRATE_KEPT_FILES = ["crew/crew_hook.py", "crew/spec_to_task_hook.py"]

# Source path -> former French path. A project that still has the French-named file keeps
# being updated in place (never gets a duplicate under the English name); see migrate_names().
PATH_ALIASES = {"crew/CLAUDE_CONTEXT/LIFECYCLE.md": "crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md"}


def project_path(project_root, rel):
    """Where `rel` (a source path) lives in the project: the legacy French name when
    only that one exists, otherwise `rel` itself."""
    legacy = PATH_ALIASES.get(rel)
    root = pathlib.Path(project_root)
    if legacy and not (root / rel).exists() and (root / legacy).exists():
        return legacy
    return rel


def legacy_persona_files(project_root, source_root=None):
    """Legacy personas (`.claude/agents/*.md`) derived from a glob over the
    target project and, if given, the source: adding a persona to the
    scaffold needs no list edit. Union of both sides so a new persona
    (source only) is created and a persona removed from the source (project
    only) is still detected as `removed`."""
    roots = [r for r in (project_root, source_root) if r is not None]
    names = {p.name for r in roots for p in (pathlib.Path(r) / ".claude/agents").glob("*.md")}
    return [f".claude/agents/{n}" for n in sorted(names)]


def hash_file(path):
    """sha256 hash of the content, or None if the file does not exist."""
    path = pathlib.Path(path)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(local_hash, recorded_hash, source_hash):
    """Pure decision for one engine file, with no disk access.

    - "absent"    : exists neither locally nor in the source (nothing to do).
    - "new"       : absent locally, present in the source -> to create.
    - "removed"   : present locally, gone from the source (moved or deleted
                    upstream) -> never applied automatically (nothing to
                    copy), reported for a manual decision.
    - "up_to_date": local already identical to the source -> no-op.
    - "apply"     : local unchanged since our last known write
                    (recorded_hash) but the source evolved -> safe to overwrite.
    - "conflict"  : local differs from the last known write -> a user
                    customization is possible, never overwrite silently.
    """
    if local_hash is None:
        return "new" if source_hash is not None else "absent"
    if source_hash is None:
        return "removed"
    if local_hash == source_hash:
        return "up_to_date"
    if local_hash == recorded_hash:
        return "apply"
    return "conflict"


def load_scaffold_version(project_root):
    p = pathlib.Path(project_root) / SCAFFOLD_VERSION_REL
    if not p.is_file():
        return {"version": None, "files": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json_atomic(path, data, **dumps_kw):
    """temp file + os.replace: never a truncated JSON if the process is killed."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, **dumps_kw) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def save_scaffold_version(project_root, data):
    """Atomic write (temp file + os.replace), same idiom as
    crew_hook.save_locks(): avoids a truncated SCAFFOLD_VERSION.json if the
    process is killed mid-write (it is re-read on every following
    /crew-update to decide apply vs conflict)."""
    p = pathlib.Path(project_root) / SCAFFOLD_VERSION_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(p, data, sort_keys=True)


def plan(project_root, source_root, whitelist):
    """Per-file decision over the allowlist, writing nothing."""
    project_root = pathlib.Path(project_root)
    source_root = pathlib.Path(source_root)
    recorded = load_scaffold_version(project_root).get("files", {})
    decisions = []
    for rel in whitelist:
        dest = project_path(project_root, rel)
        local_hash = hash_file(project_root / dest)
        source_hash = hash_file(source_root / rel)
        recorded_hash = recorded.get(dest)
        decisions.append({
            "path": rel,
            "dest": dest,
            "status": classify(local_hash, recorded_hash, source_hash),
            "local_hash": local_hash,
            "source_hash": source_hash,
        })
    return decisions


def apply(project_root, source_root, decisions):
    """Writes only files with status 'apply'/'new'. Returns the list of
    relative paths actually written."""
    project_root = pathlib.Path(project_root)
    source_root = pathlib.Path(source_root)
    applied = []
    for d in decisions:
        if d["status"] not in ("apply", "new"):
            continue
        dest = d.get("dest", d["path"])
        dst = project_root / dest
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / d["path"], dst)
        applied.append(dest)
    return applied


def detect_mode(project_root, user_settings_path=None, env=None, source_root=None):
    """Install mode of the target project:
    - "plugin"  : no local copy of the crew skills/personas (served from
                  ${CLAUDE_PLUGIN_ROOT}, nothing to sync for them);
    - "migrate" : local copies (bootstrapped before the plugin) AND the
                  crew-mates plugin installed -> both load, the copies are
                  duplicates to remove (plan_migration());
    - "legacy"  : local copies without the plugin (manual clone), or the
                  scaffold source repo itself (its .claude/ copies are the
                  dogfood sources, never purged).
    Local copies = a `.claude/skills/crew-*/SKILL.md`, or (with `source_root`, the plugin
    root) any plugin-served skill/persona still copied locally, e.g. personas kept after a
    partial migration."""
    if is_scaffold_source(project_root):
        return "legacy" if _has_local_copy_marker(project_root) else "plugin"
    installed = plugin_installed(project_root, user_settings_path, env)
    if _has_local_copy_marker(project_root):
        return "migrate" if installed else "legacy"
    if installed and source_root is not None and local_copy_units(project_root, source_root):
        return "migrate"
    return "plugin"


def is_scaffold_source(project_root):
    """True for the crew-mates repo itself (`.claude-plugin/plugin.json` named crew-mates)."""
    manifest = _read_settings(pathlib.Path(project_root) / ".claude-plugin" / "plugin.json")
    return manifest.get("name") == PLUGIN_NAME


def plugin_installed(project_root, user_settings_path=None, env=None):
    """True if the crew-mates plugin serves this project: CLAUDE_PLUGIN_ROOT set, otherwise
    what the settings say (plugin_enabled_in_settings)."""
    env = os.environ if env is None else env
    return bool(env.get("CLAUDE_PLUGIN_ROOT")) or plugin_enabled_in_settings(project_root, user_settings_path)


def plugin_enabled_in_settings(project_root, user_settings_path=None):
    """The first `enabledPlugins` entry for crew-mates found in settings.local.json >
    settings.json > user settings: the most specific scope wins, so a project-level `false`
    beats a user `true`. False when no scope mentions it."""
    claude_dir = pathlib.Path(project_root) / ".claude"
    scopes = [claude_dir / name for name in reversed(PROJECT_SETTINGS_FILES)]
    scopes.append(user_settings_path or USER_SETTINGS_PATH)
    for path in scopes:
        state = _plugin_state(_read_settings(path))
        if state is not None:
            return state
    return False


def seed(project_root, whitelist, version, force=False):
    """Seeds SCAFFOLD_VERSION.json on a legacy project that does not have one
    yet: accepts the current local content of each present file as "our last
    known write". Without this seeding, the first plan() of a legacy project
    classifies every diverging file as "conflict" (no recorded_hash to prove
    the absence of customization) and /crew-update applies nothing
    automatically on the first run.

    Refuses to overwrite an already recorded history unless force=True:
    unlike record_version() which merges, seed() starts from a blank slate
    and would otherwise silently lose the existing hashes."""
    project_root = pathlib.Path(project_root)
    existing = load_scaffold_version(project_root)
    if not force and existing.get("files"):
        raise ValueError(
            "SCAFFOLD_VERSION.json already exists with recorded hashes — "
            "seed() would overwrite them. Use plan()/apply()/record_version() "
            "for a normal update, or pass force=True to deliberately "
            "re-seed the baseline."
        )
    files = {}
    for rel in whitelist:
        dest = project_path(project_root, rel)
        h = hash_file(project_root / dest)
        if h is not None:
            files[dest] = h
    data = {"version": version, "files": files}
    save_scaffold_version(project_root, data)
    return data


def record_version(project_root, source_version, decisions):
    """Bumps the recorded version and the hash of the files actually applied
    (conflicts keep their previously recorded hash)."""
    data = load_scaffold_version(project_root)
    files = data.setdefault("files", {})
    for d in decisions:
        if d["status"] in ("apply", "new"):
            files[d.get("dest", d["path"])] = d["source_hash"]
    data["version"] = source_version
    save_scaffold_version(project_root, data)
    return data


def _read_settings(path):
    """JSON of a settings.json, {} if missing/unreadable/of unexpected shape."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _plugin_state(settings):
    """True/False if `enabledPlugins` mentions crew-mates (or its former name), None if silent."""
    plugins = settings.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return None
    states = [v is True for k, v in plugins.items() if k.split("@")[0] in (PLUGIN_NAME, LEGACY_PLUGIN_NAME)]
    return any(states) if states else None


# --- migrate mode: remove the local copies the plugin already serves ----------
# Unit = one skill folder (`.claude/skills/<name>/`) or one persona (`.claude/agents/<name>.md`):
# a kept SKILL.md never loses the reference files next to it.

SKILLS_PREFIX = ".claude/skills/"
AGENTS_PREFIX = ".claude/agents/"
# one path component, never "." / ".." nor a separator
SKILL_UNIT_RE = re.compile(r"^" + re.escape(SKILLS_PREFIX) + r"(?!\.{1,2}/$)[^/\\]+/$")
AGENT_UNIT_RE = re.compile(r"^" + re.escape(AGENTS_PREFIX) + r"[^/\\]+\.md$")


def _contained(project_root, path):
    """True if `path` really lives under the project's own `.claude/` once every link is
    resolved: a symlinked/junctioned `.claude`, `skills`, skill folder or file points
    elsewhere (a clone, a shared skills dir) and must never be listed nor deleted."""
    anchor = pathlib.Path(project_root).resolve() / ".claude"
    try:
        pathlib.Path(path).resolve().relative_to(anchor)
    except (OSError, ValueError):
        return False
    return True


def _unit_files(project_root, unit_dir):
    """Every entry under a skill folder, or None if one of them (or the folder) escapes the project."""
    entries = [unit_dir, *unit_dir.rglob("*")]
    if any(e.is_symlink() for e in entries) or not all(_contained(project_root, e) for e in entries):
        return None
    return sorted(e for e in entries if e.is_file())


def _has_local_copy_marker(project_root):
    """One of the scaffold's own skills copied locally (not only crew-init: a partly migrated
    project keeps the copies the user chose to keep). A user skill named `crew-<x>` is not one."""
    skills = pathlib.Path(project_root) / ".claude" / "skills"
    return any((skills / name / "SKILL.md").is_file() for name in LEGACY_SKILL_NAMES)


def local_copy_units(project_root, source_root):
    """Plugin-served local copies: [{"path": unit, "files": [(project rel, source rel or None)]}].
    A skill/persona the plugin does not ship is never listed; source rel None marks a file the
    user added inside a served skill folder. Anything escaping the project through a link is skipped."""
    project_root, source_root = pathlib.Path(project_root), pathlib.Path(source_root)
    units = []
    for skill_dir in sorted(p for p in (project_root / SKILLS_PREFIX).glob("*") if p.is_dir()):
        served = source_root / "skills" / skill_dir.name
        if not served.is_dir():
            continue
        files = _unit_files(project_root, skill_dir)
        if not files:  # escapes through a link (None) or empty folder
            continue
        unit = f"{SKILLS_PREFIX}{skill_dir.name}/"
        inners = [f.relative_to(skill_dir).as_posix() for f in files]
        pairs = [(unit + inner, f"skills/{skill_dir.name}/{inner}" if (served / inner).is_file() else None)
                 for inner in inners]
        units.append({"path": unit, "files": pairs})
    for agent in sorted((project_root / AGENTS_PREFIX).glob("*.md")):
        if (source_root / "agents" / agent.name).is_file() and _contained(project_root, agent):
            rel = AGENTS_PREFIX + agent.name
            units.append({"path": rel, "files": [(rel, "agents/" + agent.name)]})
    return units


def plan_migration(project_root, source_root):
    """Per unit: "remove" if every file is unchanged (hash = our last recorded write, or = the
    plugin's current file) and the user added none; "conflict" otherwise, with `changed`
    (customized or never-recorded copies) and `user_files` (the user's own files). Not the
    "removed" status of plan() (gone upstream). Writes nothing."""
    project_root, source_root = pathlib.Path(project_root), pathlib.Path(source_root)
    recorded = load_scaffold_version(project_root).get("files", {})
    decisions = []
    for unit in local_copy_units(project_root, source_root):
        changed, user_files = [], []
        for rel, source_rel in unit["files"]:
            if source_rel is None:
                user_files.append(rel)
                continue
            local = hash_file(project_root / rel)
            if local != recorded.get(rel) and local != hash_file(source_root / source_rel):
                changed.append(rel)
        decisions.append({"path": unit["path"], "status": "conflict" if changed or user_files else "remove",
                          "changed": changed, "user_files": user_files})
    return decisions


def remove_copies(project_root, units):
    """Deletes whole units (skill folder with everything in it, or one persona file), only when
    they really live in the project's `.claude/` (links refused), and forgets their hashes in
    SCAFFOLD_VERSION.json. Call only on explicit confirmation. Returns the units deleted."""
    root = pathlib.Path(project_root)
    planned = []
    for unit in units:
        target = root / unit
        files = None
        if SKILL_UNIT_RE.match(unit) and target.is_dir():
            files = _unit_files(root, target)  # None if anything in it escapes through a link
        elif AGENT_UNIT_RE.match(unit) and target.is_file() and _contained(root, target):
            files = [target]
        if files is None:
            raise ValueError(f"not a local skill folder / persona copy inside the project: {unit}")
        planned.append((unit, target, files))
    data = load_scaffold_version(root)
    recorded = data.get("files", {})
    forgotten = False
    for unit, target, files in planned:
        for f in files:
            forgotten |= recorded.pop(f.relative_to(root).as_posix(), None) is not None
        if target.is_dir():
            shutil.rmtree(target)  # link-free, checked by _unit_files
        else:
            target.unlink()
    if forgotten:
        save_scaffold_version(root, data)
    return [unit for unit, _, _ in planned]


HISTORY_DOC_RE = re.compile(r"HISTOR|ARCHIVE", re.IGNORECASE)


def _copy_ref_re(source_root):
    """Matches a concrete plugin-served copy path (`.claude/skills/<served>`,
    `.claude/agents/<served>.md`); the user's own skills/personas and a bare folder name are not."""
    source_root = pathlib.Path(source_root)
    skills = [p.name for p in (source_root / "skills").glob("*") if p.is_dir()]
    agents = [p.stem for p in (source_root / "agents").glob("*.md")]
    alts = [rf"skills/{re.escape(n)}(?![\w-])" for n in skills] + [rf"agents/{re.escape(n)}\.md" for n in agents]
    return re.compile(r"\.claude/(?:" + "|".join(alts) + ")") if alts else None


def hardcoded_copy_refs(project_root, source_root):
    """Live project docs (CLAUDE.md, AGENTS.md, crew/CLAUDE_CONTEXT/*.md, history and
    archives excluded) still naming a copy the plugin serves (see _copy_ref_re):
    [{file, line, text}], reported once the copies are gone. Read-only."""
    root = pathlib.Path(project_root)
    copy_ref = _copy_ref_re(source_root)
    if copy_ref is None:
        return []
    docs = ["CLAUDE.md", "AGENTS.md"] + sorted(
        p.relative_to(root).as_posix() for p in (root / "crew" / "CLAUDE_CONTEXT").glob("*.md")
        if not HISTORY_DOC_RE.search(p.name))
    refs = []
    for rel in docs:
        path = root / rel
        if not path.is_file():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if copy_ref.search(line):
                refs.append({"file": rel, "line": n, "text": line.strip()})
    return refs

def _is_local_crew_hook(hook):
    command = hook.get("command") if isinstance(hook, dict) else None
    return (isinstance(command, str) and "CLAUDE_PLUGIN_ROOT" not in command
            and LOCAL_HOOK_RE.search(command) is not None)


def _group_hooks(group):
    inner = group.get("hooks") if isinstance(group, dict) else None
    return inner if isinstance(inner, list) else []


def _hook_groups(settings):
    """(event, groups) for each well-formed event of `hooks`."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event, groups in hooks.items():
        if isinstance(groups, list):
            yield event, groups


def _iter_local_hook_commands(settings):
    for event, groups in _hook_groups(settings):
        for group in groups:
            for hook in _group_hooks(group):
                if _is_local_crew_hook(hook):
                    yield event, hook["command"]


def _strip_local_hooks(settings):
    """Removes the local crew hooks from `settings` (in place); only deletes
    groups/events that are empty *because of* the removal. True if modified."""
    modified = False
    for event, groups in list(_hook_groups(settings)):
        kept = []
        for group in groups:
            inner = _group_hooks(group)
            remaining = [h for h in inner
                         if not _is_local_crew_hook(h)]
            if len(remaining) != len(inner):
                modified = True
                group["hooks"] = remaining
                if not remaining:
                    continue
            kept.append(group)
        if kept:
            settings["hooks"][event] = kept
        else:
            del settings["hooks"][event]
    if modified and not settings["hooks"]:
        del settings["hooks"]
    return modified


def detect_double_hook(project_root, user_settings_path=None):
    """{event: [local commands]} when the crew-mates plugin is active
    (`enabledPlugins` of the project or the user) AND the project settings
    also call the local copy `crew/crew_hook.py`: two hooks on the same
    crew_lock.json. {} otherwise (legacy without plugin = normal).
    Read-only."""
    claude_dir = pathlib.Path(project_root) / ".claude"
    project_settings = [_read_settings(claude_dir / name) for name in PROJECT_SETTINGS_FILES]
    found = {}
    for settings in project_settings:
        for event, cmd in _iter_local_hook_commands(settings):
            found.setdefault(event, []).append(cmd)
    if not found:
        return {}
    if not plugin_enabled_in_settings(project_root, user_settings_path):
        return {}
    return found


def remove_double_hook(project_root):
    """Removes from the project settings only the local hook entries
    `crew/crew_hook.py` (the rest of the file is kept, but reformatted as
    indented JSON). Writes: call only on explicit confirmation.
    Returns the modified files."""
    changed = []
    claude_dir = pathlib.Path(project_root) / ".claude"
    for name in PROJECT_SETTINGS_FILES:
        path = claude_dir / name
        settings = _read_settings(path)
        if _strip_local_hooks(settings):
            _write_json_atomic(path, settings)
            changed.append(str(path))
    return changed


def _handle_double_hook(project_root, remove):
    """Warns about (and only removes if `remove`) a plugin + local double hook."""
    double = detect_double_hook(project_root)
    if double:
        print("WARNING: crew-mates plugin active AND local hooks crew/crew_hook.py "
              "(two hooks on the same crew_lock.json):")
        for event, cmds in double.items():
            for cmd in cmds:
                print(f"  {event}: {cmd}")
        if remove:
            for f in remove_double_hook(project_root):
                print(f"Local hooks removed from {f}")
        else:
            print("Re-run with --remove-double-hook to remove them (no changes made).")
        print()
    elif remove:
        print("--remove-double-hook: no double hook detected, nothing to remove.")


# --- Migration to the English names (optional, per project) -------------------

CONTEXT = "crew/CLAUDE_CONTEXT/"
RENAMES = [
    (CONTEXT + "HISTORIQUE_ARCHIVE.md", CONTEXT + "HISTORY_ARCHIVE.md"),
    (CONTEXT + "HISTORIQUE.md", CONTEXT + "HISTORY.md"),
    (CONTEXT + "CHANGELOG_TACHES.md", CONTEXT + "TASK_CHANGELOG.md"),
    (CONTEXT + "CYCLE_DE_VIE.md", CONTEXT + "LIFECYCLE.md"),
]
# Files whose prose mentions the renamed files (plain text replacement of the file names).
REFERENCE_FILES = ["CLAUDE.md", "AGENTS.md", "PRODUCT.md", CONTEXT + "AGENTS.md", ".gitignore"]
# Field/section labels rewritten in place: file -> [(old, new)] (plain, case-sensitive).
LABEL_REWRITES = {
    CONTEXT + "TESTS_POLICY.md": [("Niveau :", "Level:"), ("Niveau:", "Level:"),
                                   ("Zones risqu" + "\u00e9es :", "Risky zones:"), ("Zones risqu" + "\u00e9es:", "Risky zones:")],
}
UNSORTED_LEGACY_RE = re.compile(r"^(#{2,3}\s*)[A\u00c0] classer\b", re.MULTILINE | re.IGNORECASE)


def _git(project_root, *args):
    return subprocess.run(["git", *args], cwd=str(project_root), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)


def _is_tracked(project_root, rel):
    return _git(project_root, "ls-files", "--error-unmatch", "--", rel).returncode == 0


def _rename(project_root, old, new):
    """git mv for tracked files (keeps history), plain rename otherwise."""
    root = pathlib.Path(project_root)
    if _is_tracked(root, old) and _git(root, "mv", old, new).returncode == 0:
        return
    (root / new).parent.mkdir(parents=True, exist_ok=True)
    os.replace(root / old, root / new)


def _rewritten_text(project_root, rel):
    """New content of `rel` after the label/reference rewrites, or None if nothing changes."""
    path = pathlib.Path(project_root) / rel
    if not path.exists():
        return None
    raw = path.read_bytes().decode("utf-8")
    text = raw
    if rel == "crew/CLAUDE_BATCH.md":
        text = UNSORTED_LEGACY_RE.sub(r"\1Unsorted", text)
    for old, new in LABEL_REWRITES.get(rel, []):
        text = text.replace(old, new)
    if rel in REFERENCE_FILES:
        for old, new in RENAMES:
            text = text.replace(pathlib.PurePosixPath(old).name, pathlib.PurePosixPath(new).name)
    return None if text == raw else text


def migrate_names(project_root, apply=False):
    """Moves a project from the former French names (HISTORIQUE.md, CHANGELOG_TACHES.md,
    CYCLE_DE_VIE.md, the `A classer` section, `Niveau :` ...) to the English ones.
    Dry-run unless apply=True. Never overwrites: when both names exist the pair is reported
    as a conflict and left alone. Idempotent. Returns
    {"applied": bool, "actions": [{kind, from, to?}], "conflicts": [{from, to, reason}]}."""
    root = pathlib.Path(project_root)
    actions, conflicts = [], []
    for old, new in RENAMES:
        if not (root / old).exists():
            continue
        if (root / new).exists():
            conflicts.append({"from": old, "to": new, "reason": "both names exist; merge them by hand"})
            continue
        actions.append({"kind": "rename", "from": old, "to": new})
        if apply:
            _rename(root, old, new)
    candidates = list(LABEL_REWRITES) + ["crew/CLAUDE_BATCH.md"] + REFERENCE_FILES
    for rel in dict.fromkeys(candidates):
        text = _rewritten_text(root, rel)
        if text is None:
            continue
        actions.append({"kind": "rewrite", "from": rel})
        if apply:
            (root / rel).write_bytes(text.encode("utf-8"))
    if apply:
        data = load_scaffold_version(root)
        files = data.get("files", {})
        moved = {old: new for old, new in RENAMES if any(a["kind"] == "rename" and a["from"] == old for a in actions)}
        for old, new in moved.items():
            if old in files:
                files[new] = files.pop(old)
        if moved and files:
            save_scaffold_version(root, data)
    return {"applied": bool(apply), "actions": actions, "conflicts": conflicts}



def engine_whitelist(mode, project_root, source_root=None):
    """Engine files /crew-update syncs for a mode (see detect_mode()). In "migrate" the
    skills/agents come from the plugin (only offered for removal, never re-synced) and the
    local hook scripts are refreshed only where they already exist, never created."""
    whitelist = list(ENGINE_FILES_COMMON)
    if mode == "legacy":
        whitelist += ENGINE_FILES_LEGACY + legacy_persona_files(project_root, source_root)
    elif mode == "migrate":
        whitelist += [rel for rel in MIGRATE_KEPT_FILES if (pathlib.Path(project_root) / rel).is_file()]
    return whitelist


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="root of the target project")
    parser.add_argument("--source", default=None, help="root of the scaffold source (not needed with --seed)")
    parser.add_argument("--legacy", action="store_true",
                         help="force inclusion of the legacy engine files (otherwise auto-detected via detect_mode())")
    parser.add_argument("--apply", action="store_true",
                         help="actually write the 'apply'/'new' files (otherwise dry-run)")
    parser.add_argument("--source-version", default=None,
                         help="version to record after applying (e.g. from .claude-plugin/plugin.json)")
    parser.add_argument("--seed", action="store_true",
                         help="seed SCAFFOLD_VERSION.json on a legacy project with no history "
                              "(accepts the current local content as baseline), then exit without comparing to the source")
    parser.add_argument("--force", action="store_true",
                         help="with --seed, deliberately re-seed an already recorded baseline")
    parser.add_argument("--migrate-names", action="store_true",
                         help="rename the former French files/labels to their English names "
                              "(dry-run unless --apply); all collaborators must run a plugin that understands both")
    parser.add_argument("--remove-double-hook", action="store_true",
                         help="remove the local crew/crew_hook.py hooks from the project settings "
                              "when the crew-mates plugin is also active (otherwise: warning only)")
    parser.add_argument("--remove-local-copies", action="store_true",
                         help="migrate mode only: delete the unchanged local skill/agent copies "
                              "the crew-mates plugin already serves (otherwise: listed only)")
    parser.add_argument("--remove-copy", action="append", default=[], metavar="PATH",
                         help="migrate mode only: also delete this customized copy (repeatable)")
    args = parser.parse_args()

    removing = args.remove_local_copies or bool(args.remove_copy)
    if removing and (args.migrate_names or args.seed):
        parser.error("--remove-local-copies/--remove-copy cannot be combined with --migrate-names or --seed")

    if args.migrate_names:
        report = migrate_names(args.project, apply=args.apply)
        for a in report["actions"]:
            print(f"{a['kind']:>8}  {a['from']}" + (f"  ->  {a['to']}" if "to" in a else ""))
        for c in report["conflicts"]:
            print(f"conflict  {c['from']}  ->  {c['to']}  ({c['reason']})")
        if not report["actions"] and not report["conflicts"]:
            print("Nothing to migrate: this project already uses the English names.")
        elif args.apply:
            print("\nMigrated. Commit the renames, and make sure every collaborator updates the plugin "
                  "(an old crew-mates version does not know the English names).")
        else:
            print("\nDry-run — re-run with --apply to write.")
        return

    mode = "legacy" if args.legacy else detect_mode(args.project, source_root=args.source)
    if removing and (mode != "migrate" or not args.source):
        parser.error(f"--remove-local-copies/--remove-copy need migrate mode and --source (detected: {mode})")
    # validated before anything is written: a typo in --remove-copy must not leave a half-run
    migration = None
    if mode == "migrate" and args.source and not args.seed:
        migration = plan_migration(args.project, args.source)
        unknown = sorted(set(args.remove_copy) - {d["path"] for d in migration})
        if unknown:
            parser.error(f"--remove-copy: not a listed local copy: {', '.join(unknown)}")

    _handle_double_hook(args.project, args.remove_double_hook)

    whitelist = engine_whitelist(mode, args.project, args.source)

    if args.seed:
        if not args.source_version:
            parser.error("--seed requires --source-version")
        data = seed(args.project, whitelist, args.source_version, force=args.force)
        print(f"Seeded: {len(data['files'])} file(s) recorded as baseline (version {data['version']}).")
        return

    if not args.source:
        parser.error("--source is required outside --seed mode")

    decisions = plan(args.project, args.source, whitelist)
    for d in decisions:
        if d["status"] == "absent":
            continue
        print(f"{d['status']:>10}  {d['path']}")

    if args.apply:
        applied = apply(args.project, args.source, decisions)
        if args.source_version:
            record_version(args.project, args.source_version, decisions)
        print(f"\n{len(applied)} file(s) applied.")
    else:
        print("\nDry-run — re-run with --apply to write.")

    if migration is not None:
        _handle_local_copies(args, migration)


def _copy_note(d):
    if d["status"] == "remove":
        return "unchanged copy, safe to delete"
    parts = []
    if d["changed"]:
        parts.append("customized or unrecorded: " + ", ".join(d["changed"]))
    if d["user_files"]:
        parts.append("your own files, not shipped by the plugin: " + ", ".join(d["user_files"]))
    return "; ".join(parts) + " — keep it, or delete the whole unit with --remove-copy"


def _handle_local_copies(args, migration):
    """Lists the duplicated local copies; deletes only on --remove-local-copies / --remove-copy."""
    print("\nLocal skill/agent copies also served by the crew-mates plugin (loaded twice):")
    for d in migration:
        print(f"{d['status']:>10}  {d['path']}  ({_copy_note(d)})")
    if not migration:
        print("  none")
    unchanged = [d["path"] for d in migration if d["status"] == "remove"] if args.remove_local_copies else []
    targets = list(dict.fromkeys(unchanged + args.remove_copy))  # ordered, no duplicates
    if targets:
        removed = remove_copies(args.project, targets)
        print(f"\n{len(removed)} local copy unit(s) deleted. Restart Claude Code, then commit the deletions.")
    elif migration:
        print("\nNothing deleted — re-run with --remove-local-copies (and --remove-copy PATH "
              "for a customized one) after confirmation.")
    refs = hardcoded_copy_refs(args.project, args.source)
    if refs:
        print("\nProject docs still pointing at local copies (update them by hand):")
        for r in refs:
            print(f"  {r['file']}:{r['line']}  {r['text']}")

if __name__ == "__main__":
    _main()

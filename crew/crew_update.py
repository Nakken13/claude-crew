# -*- coding: utf-8 -*-
"""Update engine for the crew scaffold on an already-bootstrapped project
(task mecanisme-mise-a-jour-scaffold-multi-projets).

For each "engine" file in an allowlist, compares the target project's local
content with the scaffold source, relying on a hash recorded at the last
write (crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json) so a user customization is
never silently overwritten.

Never writes to user data folders (crew/TODO, crew/CURRENT_TASKS,
crew/PROBLEMS, crew/ICEBOX, crew/TESTS, crew/CLAUDE_CONTEXT/HISTORIQUE.md,
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
    "crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md",
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
]

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
        local_hash = hash_file(project_root / rel)
        source_hash = hash_file(source_root / rel)
        recorded_hash = recorded.get(rel)
        decisions.append({
            "path": rel,
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
        dst = project_root / d["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / d["path"], dst)
        applied.append(d["path"])
    return applied


def detect_mode(project_root):
    """"legacy" if the target project has a local copy of the crew-*
    skills/agents (bootstrapped before the plugin repackaging, see
    skills/crew-*), "plugin" otherwise (skills/agents/hooks served from
    ${CLAUDE_PLUGIN_ROOT}, nothing to sync for them)."""
    marker = pathlib.Path(project_root) / ".claude" / "skills" / "crew-init" / "SKILL.md"
    return "legacy" if marker.is_file() else "plugin"


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
        h = hash_file(project_root / rel)
        if h is not None:
            files[rel] = h
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
            files[d["path"]] = d["source_hash"]
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


def _plugin_enabled(settings):
    plugins = settings.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return False
    return any(k.split("@")[0] in (PLUGIN_NAME, LEGACY_PLUGIN_NAME) and v is True for k, v in plugins.items())


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
    if not any(_plugin_enabled(s) for s in project_settings) and not _plugin_enabled(
            _read_settings(user_settings_path or USER_SETTINGS_PATH)):
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
    parser.add_argument("--remove-double-hook", action="store_true",
                         help="remove the local crew/crew_hook.py hooks from the project settings "
                              "when the crew-mates plugin is also active (otherwise: warning only)")
    args = parser.parse_args()

    _handle_double_hook(args.project, args.remove_double_hook)

    whitelist = list(ENGINE_FILES_COMMON)
    if args.legacy or detect_mode(args.project) == "legacy":
        whitelist += ENGINE_FILES_LEGACY + legacy_persona_files(args.project, args.source)

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


if __name__ == "__main__":
    _main()

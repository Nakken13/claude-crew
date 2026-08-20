#!/usr/bin/env python3
"""Structural integrity checks for the claude-crew plugin package.

Run directly: python scripts/dev/verify_plugin_package.py
Exits 0 if every check passes, 1 otherwise (with problems printed).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _content_equal(path_a: Path, path_b: Path) -> bool:
    """Byte-for-byte compare, tolerant of CRLF/LF checkout normalization.

    A plain filecmp.cmp on Windows checkouts can report a false mismatch
    when one file was freshly checked out (CRLF, per core.autocrlf) and the
    other has sat untouched since an earlier checkout (LF) — same content,
    different line endings. Normalize both before comparing.
    """
    a = path_a.read_bytes().replace(b"\r\n", b"\n")
    b = path_b.read_bytes().replace(b"\r\n", b"\n")
    return a == b


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


# The exact set of files template/ is allowed to ship — intentionally a
# strict subset of $HOME/.claude/templates/project-scaffold/ (that source
# directory legitimately also contains its own .claude/ and README.md,
# which the plugin-native design deliberately excludes from template/: see
# Fix 2 in the 2026-08-20 marketplace-plugin final review). Each entry is
# verified present in template/ and byte-identical to the corresponding
# file in the source scaffold.
TEMPLATE_WHITELIST = [
    "CLAUDE.md",
    "AGENTS.md",
    "PRODUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "check_placeholders.py",
    ".gitignore",
    "crew/CLAUDE_BATCH.md",
    "crew/CLAUDE_CONTEXT/AGENTS.md",
    "crew/CLAUDE_CONTEXT/HISTORIQUE.md",
    "crew/CLAUDE_CONTEXT/TESTS_DONE/README.md",
    "crew/CURRENT_TASKS/README.md",
    "crew/ICEBOX/README.md",
    "crew/PROBLEMS/README.md",
    "crew/TESTS/README.md",
    "crew/TESTS/IA/README.md",
    "crew/TESTS/DEV/README.md",
    "crew/TODO/README.md",
]


def check_template_matches_source(repo_root: Path) -> list[str]:
    problems = []
    template_dir = repo_root / "template"
    source_dir = Path.home() / ".claude" / "templates" / "project-scaffold"

    if not template_dir.exists():
        problems.append(f"missing {template_dir}")
        return problems
    if not source_dir.exists():
        print(f"info: source scaffold not found at {source_dir} — skipping drift check")
        return problems

    for rel in TEMPLATE_WHITELIST:
        template_file = template_dir / rel
        source_file = source_dir / rel
        if not template_file.exists():
            problems.append(f"missing {template_file}")
            continue
        if not source_file.exists():
            problems.append(f"source missing {source_file} (cannot verify {template_file})")
            continue
        if not _content_equal(source_file, template_file):
            problems.append(f"content differs from source scaffold: {rel}")
    return problems


ENGINE_FILE_PAIRS = [
    (".claude/skills/crew-close-task/SKILL.md", "skills/crew-close-task/SKILL.md"),
    # crew-init is intentionally excluded: it was copied byte-for-byte in Task
    # 3, but Task 5 rewrote skills/crew-init/SKILL.md in place for
    # plugin-native install, so it no longer matches .claude/skills/crew-init/
    # by design. check_crew_init_is_plugin_native covers its correctness now.
    (".claude/skills/crew-new-task/SKILL.md", "skills/crew-new-task/SKILL.md"),
    (".claude/skills/crew-start/SKILL.md", "skills/crew-start/SKILL.md"),
    (".claude/skills/crew-status/SKILL.md", "skills/crew-status/SKILL.md"),
    (".claude/agents/architect.md", "agents/architect.md"),
    (".claude/agents/ceo.md", "agents/ceo.md"),
    (".claude/agents/comms.md", "agents/comms.md"),
    (".claude/agents/manager.md", "agents/manager.md"),
    # crew/crew_hook.py and crew/spec_to_task_hook.py are intentionally
    # excluded: the plugin-distributed copies under scripts/ must resolve
    # the target project's directory via CLAUDE_PROJECT_DIR (see Fix 1 /
    # check_scripts_resolve_project_dir), which this repo's own dogfood
    # copies under crew/ do not need and must not gain (they stay
    # byte-identical to before this branch, per repo policy). So the two
    # copies diverge by design and are no longer compared byte-for-byte
    # here.
]


def check_engine_files_copied(repo_root: Path) -> list[str]:
    problems = []
    for source_rel, target_rel in ENGINE_FILE_PAIRS:
        source = repo_root / source_rel
        target = repo_root / target_rel
        if not target.exists():
            problems.append(f"missing {target}")
        elif not source.exists():
            problems.append(f"source missing {source}")
        elif not _content_equal(source, target):
            problems.append(f"content mismatch: {target} differs from {source}")
    return problems


EVENT_EXPECTED_SCRIPT = {
    "Stop": "scripts/crew_hook.py",
    "SessionEnd": "scripts/crew_hook.py",
    "PostToolUse": "scripts/spec_to_task_hook.py",
}


def check_hooks_json(repo_root: Path) -> list[str]:
    problems = []
    hooks_path = repo_root / "hooks" / "hooks.json"
    if not hooks_path.exists():
        problems.append(f"missing {hooks_path}")
        return problems

    text = hooks_path.read_text(encoding="utf-8")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        problems.append(f"{hooks_path} is not valid JSON: {e}")
        return problems

    events = data.get("hooks", {})
    for event_name, script_rel in EVENT_EXPECTED_SCRIPT.items():
        if event_name not in events:
            problems.append(f"{hooks_path} missing event: {event_name}")
            continue
        event_text = json.dumps(events[event_name])
        if script_rel not in event_text:
            problems.append(f"{hooks_path} event {event_name} does not wire up {script_rel}")
        if not (repo_root / script_rel).exists():
            problems.append(f"{hooks_path} references {script_rel} but it does not exist")

    if "graphify" in text.lower():
        problems.append(f"{hooks_path} must not reference graphify (dogfood-only, not product surface)")

    return problems


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


def check_readme_has_marketplace_install(repo_root: Path) -> list[str]:
    problems = []
    readme = repo_root / "README.md"
    text = readme.read_text(encoding="utf-8")
    if "/plugin marketplace add Nakken13/claude-crew" not in text:
        problems.append(f"{readme} missing the /plugin marketplace add command")
    if "/plugin install claude-crew@claude-crew" not in text:
        problems.append(f"{readme} missing the /plugin install command")
    return problems


def check_scripts_resolve_project_dir(repo_root: Path) -> list[str]:
    problems = []
    for script_rel in ("scripts/crew_hook.py", "scripts/spec_to_task_hook.py"):
        script_path = repo_root / script_rel
        if not script_path.exists():
            problems.append(f"missing {script_path}")
            continue
        text = script_path.read_text(encoding="utf-8")
        if "CLAUDE_PROJECT_DIR" not in text:
            problems.append(f"{script_path} does not reference CLAUDE_PROJECT_DIR")
    return problems


CHECKS = [
    check_manifests,
    check_template_matches_source,
    check_engine_files_copied,
    check_hooks_json,
    check_crew_init_is_plugin_native,
    check_readme_has_marketplace_install,
    check_scripts_resolve_project_dir,
]


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

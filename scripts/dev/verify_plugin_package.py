#!/usr/bin/env python3
"""Structural integrity checks for the claude-crew plugin package.

Run directly: python scripts/dev/verify_plugin_package.py
Exits 0 if every check passes, 1 otherwise (with problems printed).
"""
import filecmp
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
    for source_rel, target_rel in ENGINE_FILE_PAIRS:
        source = repo_root / source_rel
        target = repo_root / target_rel
        if not target.exists():
            problems.append(f"missing {target}")
        elif not source.exists():
            problems.append(f"source missing {source}")
        elif not filecmp.cmp(source, target, shallow=False):
            problems.append(f"content mismatch: {target} differs from {source}")
    return problems


CHECKS = [check_manifests, check_template_matches_source, check_engine_files_copied]


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

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

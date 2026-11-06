#!/usr/bin/env python3
"""Regenerate the packaged mirrors of the dogfood files.

Source of truth (edit these)         ->  generated mirror (never edit by hand)
  crew/crew_hook.py                      scripts/crew_hook.py   (ROOT line swapped)
  crew/crew_update.py                    scripts/crew_update.py
  .claude/skills/<name>/SKILL.md         skills/<name>/SKILL.md  (pairs listed in verify_plugin_package)
  .claude/agents/*.md                    agents/*.md

Usage:
  python scripts/dev/sync_engine.py            # rewrite drifted mirrors
  python scripts/dev/sync_engine.py --check    # exit 1 if any mirror drifted (CI / pre-commit)
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_plugin_package as vpp  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

# The only intended difference between the dogfood engine and the plugin one:
# the plugin copy must resolve the *target* project through CLAUDE_PROJECT_DIR.
_SRC_ROOT_RE = re.compile(
    r'^ROOT = pathlib\.Path\(os\.environ\.get\("CLAUDE_PROJECT_DIR"\) '
    r'or pathlib\.Path\(__file__\)\.resolve\(\)\.parent\.parent\)(?P<tail>.*)$',
    re.M,
)
PLUGIN_ROOT_LINE = (
    'ROOT = _git_root(pathlib.Path(os.environ["CLAUDE_PROJECT_DIR"])) '
    'if os.environ.get("CLAUDE_PROJECT_DIR") '
    "else pathlib.Path(__file__).resolve().parent.parent"
)


def derive_plugin_hook(src_text: str) -> str:
    """crew/crew_hook.py -> scripts/crew_hook.py (same file, plugin ROOT line)."""
    out, n = _SRC_ROOT_RE.subn(lambda m: PLUGIN_ROOT_LINE + m.group("tail"), src_text, count=1)
    if n != 1:
        raise ValueError("crew_hook.py: dogfood ROOT line not found; update sync_engine._SRC_ROOT_RE")
    return out


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _planned(repo: Path) -> dict[str, bytes]:
    """{mirror path relative to repo (posix): expected LF content}."""
    plan: dict[str, bytes] = {}

    def add(src_rel, dst_rel, transform=None):
        src = repo / src_rel
        if not src.exists():
            return  # verify_plugin_package reports a missing source
        data = _norm(src.read_bytes())
        if transform:
            data = transform(data.decode("utf-8")).encode("utf-8")
        plan[dst_rel] = data

    add("crew/crew_hook.py", "scripts/crew_hook.py", derive_plugin_hook)
    for src_rel, dst_rel in vpp.CREW_SCRIPT_PAIRS + vpp.ENGINE_FILE_PAIRS:
        add(src_rel, dst_rel)
    agents = repo / ".claude" / "agents"
    if agents.exists():
        for p in sorted(agents.glob("*.md")):
            add(f".claude/agents/{p.name}", f"agents/{p.name}")
    return plan


def sync(repo: Path = REPO_ROOT, check: bool = False) -> list[str]:
    """Bring mirrors in line with their sources. Returns the paths that drifted
    (and, unless `check`, were rewritten). Line endings of an existing mirror are
    preserved, so a CRLF checkout is never reported as drift."""
    changed = []
    plan = _planned(repo)
    for rel, expected in plan.items():
        dst = repo / rel
        current = dst.read_bytes() if dst.exists() else None
        if current is not None and _norm(current) == expected:
            continue
        changed.append(rel)
        if not check:
            crlf = current is not None and b"\r\n" in current
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(expected.replace(b"\n", b"\r\n") if crlf else expected)
    # Orphan packaged agents (their persona was removed from .claude/agents).
    agents_dir = repo / "agents"
    if agents_dir.exists() and (repo / ".claude" / "agents").exists():
        for p in sorted(agents_dir.glob("*.md")):
            rel = f"agents/{p.name}"
            if rel not in plan:
                changed.append(rel)
                if not check:
                    p.unlink()
    return changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report drift, change nothing, exit 1 if any")
    args = ap.parse_args(argv)
    changed = sync(REPO_ROOT, check=args.check)
    verb = "DRIFT" if args.check else "synced"
    for rel in changed:
        print(f"{verb}: {rel}")
    if not changed:
        print("mirrors up to date")
    return 1 if (changed and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())

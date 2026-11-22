# -*- coding: utf-8 -*-
"""PostToolUse (Write) hook: superpowers spec created in docs/superpowers/specs/
→ automatically creates the matching DRAFT task in crew/TODO/<slug>.md.

The task carries `**Status:** 📝 draft`: the engine (`next-task`) never starts it, and `lint` flags it,
until Zone/Actions/Acceptance are filled and the marker is removed.
Idempotent: does nothing if the slug is already tracked (TODO, CURRENT_TASKS, PAUSED, or closed in the
history / its archive).
"""
import json
import os
import re
import sys
from pathlib import Path

def _git_root(start):
    """First git root (folder or worktree `.git` file) walking up from `start`.
    A session launched in a subfolder (backend/, frontend/) must not create a
    phantom `crew/` there: if no `.git` is found, `start` is returned as is."""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


ROOT = _git_root(Path(os.environ["CLAUDE_PROJECT_DIR"])) if os.environ.get("CLAUDE_PROJECT_DIR") else Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "docs" / "superpowers" / "specs"
CREW = ROOT / "crew"
TODO = CREW / "TODO"
CTX = CREW / "CLAUDE_CONTEXT"
# English name first; the legacy French name is read only while the English one does not exist
# (same rule as crew_hook._ctx_file).
LEGACY_NAMES = {"HISTORY.md": "HISTORIQUE.md", "HISTORY_ARCHIVE.md": "HISTORIQUE_ARCHIVE.md"}


def _ctx_file(canonical):
    new, old = CTX / canonical, CTX / LEGACY_NAMES[canonical]
    return old if (old.exists() and not new.exists()) else new


def _closed_in_history(slug):
    """True if a `## <slug> — date` heading (outside HTML comments) exists in the history or its archive.
    Same heading rule as crew_hook._history_slugs: first word of the heading, `*`/backticks stripped."""
    for canonical in LEGACY_NAMES:
        try:
            text = _ctx_file(canonical).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"^## (.+)$", re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL), re.MULTILINE):
            if m.group(1).split()[0].strip("`*").removesuffix(".md") == slug:
                return True
    return False


def _already_tracked(slug):
    return any((CREW / d / f"{slug}.md").exists() for d in ("TODO", "CURRENT_TASKS", "PAUSED", "ICEBOX", "PROBLEMS")) \
        or _closed_in_history(slug)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    tool_input = data.get("tool_input") or {}
    raw = str(tool_input.get("file_path") or "")
    if not raw:
        return

    spec = Path(raw)
    if not spec.is_absolute():
        spec = ROOT / raw
    try:
        spec = spec.resolve()
        spec.relative_to(SPECS_DIR.resolve())
    except (ValueError, OSError):
        return
    if spec.suffix.lower() != ".md":
        return

    # 2026-07-11-personalized-tips-checklist-design.md → personalized-tips-checklist
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", spec.stem)
    slug = re.sub(r"-design$", "", slug)
    if not slug or _already_tracked(slug):
        return  # task already tracked, do not duplicate

    # Title = first H1 heading of the spec, without the "— Design" suffix
    title = slug.replace("-", " ")
    try:
        for line in spec.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = re.sub(r"\s*[—-]\s*Design\s*$", "", line[2:].strip())
                break
    except OSError:
        pass

    # Built from SPECS_DIR, not ROOT: still valid when docs/ is a symlink/junction outside the project.
    spec_rel = f"docs/superpowers/specs/{spec.relative_to(SPECS_DIR.resolve()).as_posix()}"
    from datetime import date

    task_path = TODO / f"{slug}.md"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        f"""# {title}

**Status:** 📝 draft (spec generated on {date.today().strftime('%d/%m/%Y')}) — not startable until this line is removed
**Spec :** `{spec_rel}`
Zone : <backticked paths to fill>

## Description

Task created automatically from the superpowers spec. See the spec for the full context.

## Actions

- [ ] Break the spec down into concrete actions (replace this line)

## Acceptance

- <observable success criteria to fill>

Verification: <command that proves it, to fill>
""",
        encoding="utf-8",
    )

    rel = f"crew/TODO/{slug}.md"
    print(
        json.dumps(
            {
                "systemMessage": f"Spec → draft task created: {rel}",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"A draft task {rel} was just created automatically from the spec {spec_rel}. "
                        "It is NOT startable yet. To make it startable: fill its `Zone :` line (backticked paths), "
                        "its Actions with the concrete steps from the spec, its `## Acceptance` section and its "
                        "`Verification:` line; add the task to crew/CLAUDE_BATCH.md (batching rule); then remove "
                        "the `**Status:** 📝 draft` line."
                    ),
                },
            }
        )
    )


if __name__ == "__main__":
    main()

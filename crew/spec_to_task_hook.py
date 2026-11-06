# -*- coding: utf-8 -*-
"""PostToolUse (Write) hook: superpowers spec created in docs/superpowers/specs/
→ automatically creates the matching task in crew/CURRENT_TASKS/<slug>.md.

Idempotent: does nothing if the task already exists (CURRENT_TASKS or TODO).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "docs" / "superpowers" / "specs"
CURRENT = ROOT / "crew" / "CURRENT_TASKS"
TODO = ROOT / "crew" / "TODO"


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
    if not slug:
        return

    task_path = CURRENT / f"{slug}.md"
    if task_path.exists() or (TODO / f"{slug}.md").exists():
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

    spec_rel = spec.relative_to(ROOT).as_posix()
    from datetime import date

    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        f"""# {title}

**Status:** 🟡 in progress (spec generated on {date.today().strftime('%d/%m/%Y')})
**Spec :** `{spec_rel}`

## Description

Task created automatically from the superpowers spec. See the spec for the full context.

## Actions

- [ ] Break the spec down into concrete actions (replace this line)
""",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "systemMessage": f"Spec → task created: crew/CURRENT_TASKS/{slug}.md",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"A task crew/CURRENT_TASKS/{slug}.md was just created automatically "
                        f"from the spec {spec_rel}. Fill in its Actions section with the concrete steps "
                        "from the spec, and reference the task in crew/CLAUDE_BATCH.md (batching rule)."
                    ),
                },
            }
        )
    )


if __name__ == "__main__":
    main()

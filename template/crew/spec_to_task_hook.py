# -*- coding: utf-8 -*-
"""Hook PostToolUse (Write) : spec superpowers créée dans docs/superpowers/specs/
→ crée automatiquement la tâche associée dans crew/CURRENT_TASKS/<slug>.md.

Idempotent : ne fait rien si la tâche existe déjà (CURRENT_TASKS ou TODO).
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

    # 2026-07-11-checklist-conseils-personnalises-design.md → checklist-conseils-personnalises
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", spec.stem)
    slug = re.sub(r"-design$", "", slug)
    if not slug:
        return

    task_path = CURRENT / f"{slug}.md"
    if task_path.exists() or (TODO / f"{slug}.md").exists():
        return  # tâche déjà suivie, ne pas dupliquer

    # Titre = premier heading H1 de la spec, sans le suffixe « — Design »
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

**Statut :** 🟡 en cours (spec générée le {date.today().strftime('%d/%m/%Y')})
**Spec :** `{spec_rel}`

## Description

Tâche créée automatiquement depuis la spec superpowers. Voir la spec pour le contexte complet.

## Actions

- [ ] Décliner la spec en actions concrètes (remplacer cette ligne)
""",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "systemMessage": f"Spec → tâche créée : crew/CURRENT_TASKS/{slug}.md",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"Une tâche crew/CURRENT_TASKS/{slug}.md vient d'être créée automatiquement "
                        f"depuis la spec {spec_rel}. Complète sa section Actions avec les étapes concrètes "
                        "de la spec, et référence la tâche dans crew/CLAUDE_BATCH.md (règle de batching)."
                    ),
                },
            }
        )
    )


if __name__ == "__main__":
    main()

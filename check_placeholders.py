# -*- coding: utf-8 -*-
"""Garde-fou bootstrap : liste les placeholders `<...>` non résolus dans les
fichiers du scaffold (CLAUDE.md, AGENTS.md, PRODUCT.md, CONTRIBUTING.md,
SECURITY.md, organized/**). À lancer juste après avoir rempli le scaffold, avant
de committer — un bootstrap n'est "fini" que quand cette commande n'affiche
rien.

Usage : python check_placeholders.py
Exit code 1 si des placeholders restent (utilisable en pre-commit/CI).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TARGETS = ["CLAUDE.md", "AGENTS.md", "PRODUCT.md", "CONTRIBUTING.md", "SECURITY.md", "organized"]
PLACEHOLDER = re.compile(r"<[A-Z][A-Z0-9_ /.]*>")
# Faux positifs légitimes : exemples de syntaxe montrés dans les squelettes
ALLOWLIST = {"<A>", "<B>", "<...>"}


def main():
    hits = []
    for name in TARGETS:
        p = ROOT / name
        paths = [p] if p.is_file() else (p.rglob("*.md") if p.is_dir() else [])
        for f in paths:
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for m in PLACEHOLDER.finditer(line):
                    if m.group(0) in ALLOWLIST:
                        continue
                    hits.append(f"{f.relative_to(ROOT)}:{i}: {m.group(0)}")

    if hits:
        print("Placeholders non résolus :")
        for h in hits:
            print(f"  {h}")
        sys.exit(1)
    print("OK — aucun placeholder restant.")


if __name__ == "__main__":
    main()

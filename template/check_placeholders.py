# -*- coding: utf-8 -*-
"""Bootstrap guard: lists unresolved `<...>` placeholders in the scaffold
files (CLAUDE.md, AGENTS.md, PRODUCT.md, CONTRIBUTING.md, SECURITY.md,
crew/**). Run it right after filling in the scaffold, before committing — a
bootstrap is only "done" when this command prints nothing.

Usage: python check_placeholders.py
Exit code 1 if placeholders remain (usable in pre-commit/CI).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TARGETS = ["CLAUDE.md", "AGENTS.md", "PRODUCT.md", "CONTRIBUTING.md", "SECURITY.md", "crew"]
PLACEHOLDER = re.compile(r"<[A-Z][A-Z0-9_ /.]*>")
# Legitimate false positives: syntax examples shown in the skeletons
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
        print("Unresolved placeholders:")
        for h in hits:
            print(f"  {h}")
        sys.exit(1)
    print("OK — no placeholder left.")


if __name__ == "__main__":
    main()

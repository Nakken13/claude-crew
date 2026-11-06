# Contributing to crew-mates

Community-maintained project, light on process. If you're opening a PR:

## Branches

No naming convention enforced; `feat/<slug>`/`fix/<slug>` if you want a default.

## Commits

Conventional Commits preferred (`feat:`, `fix:`, `docs:`, `refactor:`, ...)
but not required — a clear message explaining the *why* is enough.

## Pull requests

Open against `main`. Keep the diff scoped to one change; explain what
problem it solves and how you tested it. CI (`.github/workflows/ci.yml`) runs the
Python tests on Linux and Windows, the package verifier, the mirror check and the
mod tests; it must be green.

## Local setup

```bash
python -m pip install pytest -r scripts/dashboard/requirements.txt -r scripts/dashboard/requirements-dev.txt
python -m pytest crew scripts -q
python scripts/dev/verify_plugin_package.py
```

The mod tests (`hooks/mods.test.ts`) import `claude-code/testing`, which only
exists inside Claude Code; to run them with bun, copy `hooks/` somewhere and
replace that import with `bun:test` (see the `mods` job in the CI workflow).

## Packaged mirrors are generated

Some files exist twice: the copy this repo dogfoods (`crew/`, `.claude/`) and the
copy the plugin ships (`scripts/`, `skills/`, `agents/`). **Edit the dogfood copy
only**, then run `python scripts/dev/sync_engine.py`. `--check` exits 1 on drift,
and `python scripts/dev/verify_plugin_package.py` fails on it too.

## Versioning the scaffold

The scaffold's version lives in the `version` field of
[`.claude-plugin/plugin.json`](./.claude-plugin/plugin.json) — the single
source of truth, not a separate `VERSION` file. Bump convention (semver):

- **patch** — hook/skill fix, no structural change.
- **minor** — new skill, agent, or rule added.
- **major** — breaking structural change to `crew/` or `CLAUDE.md`.

Every bump gets an entry in [`CHANGELOG.md`](./CHANGELOG.md). Projects
already bootstrapped via `/crew-init` pick up engine-file changes with
`/crew-update` (see [`README.md`](./README.md)) — it never touches your
`crew/` task data and never silently overwrites a file you've personalized.

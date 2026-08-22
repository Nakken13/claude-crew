# Contributing to claude-crew

Solo-maintained project — no rigid convention imposed. That said, if you're
opening a PR:

## Branches

No naming convention enforced; `feat/<slug>`/`fix/<slug>` if you want a default.

## Commits

Conventional Commits preferred (`feat:`, `fix:`, `docs:`, `refactor:`, ...)
but not required — a clear message explaining the *why* is enough.

## Pull requests

Open against `main`. Keep the diff scoped to one change; explain what
problem it solves and how you tested it. No CI gate yet — review happens
on the PR itself.

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

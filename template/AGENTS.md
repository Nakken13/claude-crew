# AGENTS.md — <NOM_PROJET>

Invariants guide + repo map for any agent (Claude Code or other) working on
this project. Fill in/check before the first real work item — do not leave an
unresolved `<...>` placeholder.

## Stack

<List the stack actually verified from the manifest files (package.json,
requirements.txt, go.mod, Cargo.toml...), no guesses.>

## Repository map

```text
<tree of significant folders, with a one-line role for each>
```

## Verified commands

```bash
<install>
<local dev/run>
<tests>
<build>
```

Every command listed here must have been run successfully at least once —
do not document an untested command.

## Code rules

<Project-specific conventions: structure of routes/handlers, validation
schemas, logging style, what must never be done (e.g. no debug print, no
logged secret, no destructive migration without agreement).>

## Secrets and boundaries

<Where secrets live (env vars, vault...), what must never reach the
client/logs, reference to SECURITY.md if present.>

## Documentation routing

- Product vision / scope: `PRODUCT.md` (if present).
- Contribution conventions: `CONTRIBUTING.md` (if present).
- Security limits: `SECURITY.md` (if present).
- Global context guide: `crew/CLAUDE_CONTEXT/AGENTS.md`.

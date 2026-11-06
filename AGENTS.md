# AGENTS.md — crew-mates

Guide for any agent (Claude Code or other) working on this repository.

## Stack

- Python 3.11+ standard library for the engine (`crew/crew_hook.py`, `crew/crew_update.py`, `crew/spec_to_task_hook.py`); FastAPI/uvicorn only for the optional dashboard (`scripts/dashboard/`).
- TypeScript Zero-Token mods for Claude Code (`hooks/register.ts`, `hooks/mods/*.ts`), no build step.
- Markdown skills (`skills/`, `.claude/skills/`) and personas (`agents/`, `.claude/agents/`).

## Repository map

```text
.claude-plugin/     plugin.json + marketplace.json (version lives in plugin.json only)
crew/               dogfood engine + tests (SOURCE OF TRUTH for the engine)
scripts/            packaged engine copy (GENERATED), dashboard, dev tools
.claude/skills|agents/  dogfood skills/personas (SOURCE OF TRUTH)
skills/ agents/     packaged copies (GENERATED, except skills/crew-init which is plugin-native)
hooks/              hooks.json + TypeScript mods and their tests
template/           files copied into a user's project by /crew-init
docs/               design notes
```

## Verified commands

```bash
python -m pip install pytest -r scripts/dashboard/requirements.txt -r scripts/dashboard/requirements-dev.txt
python -m pytest crew scripts -q
python scripts/dev/verify_plugin_package.py
python scripts/dev/sync_engine.py          # regenerate packaged copies; --check to only report drift
claude plugin validate .
```

Mod tests need bun and an import swap (`claude-code/testing` → `bun:test`); see `CONTRIBUTING.md`.

## Code rules

- **Never edit a generated mirror** (`scripts/crew_hook.py`, `scripts/crew_update.py`, `skills/*` except `crew-init`, `agents/*`): edit the source, then run `sync_engine.py`.
- Every `subprocess` call in the engine pins stdin/stdout/stderr (a test enforces it).
- Do not rename or translate on-disk/parsed tokens (`Zone :`, `À classer`, `HISTORIQUE.md`, `Niveau :`, ...): existing projects depend on them.
- Test first; user-visible change → entry under `## [Unreleased]` in `CHANGELOG.md`.

## Secrets and boundaries

No secrets in this repo. Hooks run locally and make no network calls; see `SECURITY.md`.

## Documentation routing

- Product vision / scope: `PRODUCT.md`.
- Contribution conventions: `CONTRIBUTING.md`.
- Security: `SECURITY.md`.
- Task lifecycle, batching and context rules: `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md`; team mode and claims: `crew/CLAUDE_CONTEXT/AGENTS.md`.

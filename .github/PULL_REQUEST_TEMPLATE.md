## What and why

<!-- One change per PR. What problem does it solve? -->

## How I tested it

- [ ] `python -m pytest crew scripts -q`
- [ ] `python scripts/dev/verify_plugin_package.py`
- [ ] `python scripts/dev/sync_engine.py --check` (edit the dogfood copy, then run the sync — never edit `scripts/`, `skills/`, `agents/` by hand)
- [ ] Mods touched? `hooks/mods.test.ts` passes (see README → Testing)
- [ ] User-visible change? Entry added under `## [Unreleased]` in `CHANGELOG.md`

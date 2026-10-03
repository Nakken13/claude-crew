# Tests — identité de batch indépendante du statut

Chantier : `identite-batch-sans-statut` (hook `crew/crew_hook.py` + miroir `scripts/crew_hook.py`, skill `crew-start`).

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py scripts/dashboard/test_server.py -q` → tout vert (dont les 5 tests batch_key / status_change / legacy / different_batch).
- [ ] 🔍 `diff <(sed 's/^ROOT = .*//' crew/crew_hook.py) <(sed 's/^ROOT = .*//' scripts/crew_hook.py)` → aucune différence.
- [ ] 🔍 `diff skills/crew-start/SKILL.md .claude/skills/crew-start/SKILL.md` → identiques.
- [ ] 🔍 Changer le suffixe de statut d'un header de batch actif dans `CLAUDE_BATCH.md`, relancer un Stop → aucun `[crew_lock] incoherence` sur stderr.

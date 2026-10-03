# faux-positif-check-batches-claude-md — tests IA

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py -k check_batches -q` vert (2 tests).
- [ ] 🤖 `cmp scripts/crew_hook.py crew/crew_hook.py` sans différence.
- [ ] 🔍 Stop hook manuel (`{"hook_event_name":"Stop","session_id":"x"}`) : aucun `[batch] ... CLAUDE.md`.
- [ ] 🔍 Cas limite : `CLAUDE_BATCH.md` avec `- ~~`x.md`~~` et `- `<slug>.md`` → aucun warning.

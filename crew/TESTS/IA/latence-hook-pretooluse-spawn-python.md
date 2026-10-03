# latence-hook-pretooluse-spawn-python

Validation du pré-filtre PreToolUse (`hooks/hooks.json`, `_sync_gate_marker`
dans `scripts/crew_hook.py` + copie `crew/crew_hook.py`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 `diff scripts/crew_hook.py crew/crew_hook.py` vide ; `pytest crew/test_crew_hook.py` vert.
- [ ] 🤖 Session solo (sans `.gate_armed`) : commande shell `Edit` de `hooks.json` < 100 ms,
      aucun `crew_lock.json` créé ; marqueur présent → le script Python est bien lancé.
- [ ] 🤖 `git mv crew/TODO/x.md crew/CURRENT_TASKS/x.md` (et `crew-resume:`) sans marqueur
      atteint toujours Python et écrit le verrou ; variante chemins entre guillemets.
- [ ] 🔍 `CREW_HOOK_PROFILE=minimal` : PreToolUse sort sans spawn (shell) ; Stop/SessionEnd
      continuent de synchroniser index et verrous.
- [ ] 🔍 `verify_plugin_package.py` : aucun problème `hooks.json` (4 échecs miroirs préexistants hors périmètre).

## 🖱️ Manuel (DEV)

Voir `crew/TESTS/DEV/latence-hook-pretooluse-spawn-python.md`.

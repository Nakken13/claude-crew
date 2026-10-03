# Tests — détection double hook (plugin + copie locale)

Chantier : `detecter-double-hook-projet-cible` (`scripts/crew_update.py` + `crew/crew_update.py`, skill `crew-update`).

- [ ] 🤖 `python -m pytest crew/test_crew_update.py -q` → tout vert (cas detect plugin+local, plugin seul, legacy sans plugin, plugin désactivé, backslash Windows, formes malformées, settings.local.json, retrait sans/avec flag).
- [ ] 🔍 `diff scripts/crew_update.py crew/crew_update.py` → aucune différence.
- [ ] 🔍 `diff skills/crew-update/SKILL.md .claude/skills/crew-update/SKILL.md` → identiques.
- [ ] 🔍 Projet jetable avec `enabledPlugins: {"claude-crew@x": true}` + hook `crew/crew_hook.py` dans `.claude/settings.json` : `python scripts/crew_update.py --project <dir> --source <dir>` → avertissement, settings inchangé ; avec `--remove-double-hook` → entrée retirée, autres clés conservées.

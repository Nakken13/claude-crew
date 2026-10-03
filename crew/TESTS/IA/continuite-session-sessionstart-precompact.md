# continuite-session-sessionstart-precompact

Validation du hook `SessionStart` (digest crew) : `crew/crew_hook.py` + copie `scripts/crew_hook.py`.

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 `diff scripts/crew_hook.py crew/crew_hook.py` vide ; `pytest crew/test_crew_hook.py -k "digest or sessionstart"` vert.
- [ ] 🤖 `echo '{"hook_event_name":"SessionStart","session_id":"x"}' | python scripts/crew_hook.py` : JSON
      `hookSpecificOutput.additionalContext` ≤ 2000 chars, `crew/` inchangé (`git status crew/`).
- [ ] 🤖 Avec `CREW_SESSION_DIGEST=off` : sortie vide. Hors projet crew (pas de `crew/`) : sortie vide.
- [ ] 🔍 `python scripts/dev/verify_plugin_package.py` : aucune erreur mentionnant `SessionStart`/`hooks.json`
      (5 écarts préexistants hors périmètre : CLAUDE.md, .gitignore, crew-status, manager).

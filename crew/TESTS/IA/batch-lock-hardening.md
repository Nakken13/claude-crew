# batch-lock-hardening

Validation des 3 quick wins de durcissement du verrouillage batch multi-session
(voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md`) : mutex atomique sur
`.batch_locks.json`, garde préventive `PreToolUse` sur `git mv`
TODO->CURRENT_TASKS, `check_zone_overlaps` bloquant en cross-session.

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 Suite de smoke tests (fonctions pures, `_extract_git_mv_task`,
      `check_batch_collisions`, `check_zone_overlaps`, `LocksMutex`) — tous
      les cas passent (14 assertions au moment de l'implémentation).
- [ ] 🔍 `echo '{"session_id":"sess-test","hook_event_name":"PreToolUse",
      "tool_input":{"command":"git mv crew/TODO/<slug-inexistant>.md
      crew/CURRENT_TASKS/<slug-inexistant>.md"}}' | python crew/crew_hook.py`
      → exit code 2, stderr contient `[batch]` (tâche non catégorisée).
- [ ] 🔍 Même commande avec `"command":"ls -la"` → exit code 0, pas de
      sortie (le gate ne se déclenche que sur `git mv` TODO->CURRENT_TASKS).
- [ ] 🔍 `git mv` réel après un `mv` sans rapport dans une commande composée
      (`mv a.txt b.txt; git mv crew/TODO/x.md crew/CURRENT_TASKS/x.md`) est
      bien détecté par `_extract_git_mv_task` (pas seulement la première
      occurrence de `mv`).
- [ ] 🔍 Un chemin entre guillemets (`git mv "crew/TODO/some file.md"
      "crew/CURRENT_TASKS/some file.md"`) est correctement parsé
      (`posix=True` figé, indépendant de `sys.platform`).
- [ ] 🔍 `echo '{"session_id":"sess-test","hook_event_name":"Stop"}' | python
      crew/crew_hook.py` toujours propre (exit 0, régénère
      `BATCH_LOCKS.md`/indices, aucun mutex orphelin
      `crew/CLAUDE_CONTEXT/.batch_locks.mutex` après coup).
- [ ] 🔍 `python scripts/dev/verify_plugin_package.py` → PASS, `crew/
      crew_hook.py` et `scripts/crew_hook.py` ne divergent que sur la
      résolution `ROOT`/`CLAUDE_PROJECT_DIR` (diff des deux fichiers).
- [ ] 🔍 Stress concurrence : plusieurs threads/process appelant
      `LocksMutex()` + lecture-modification-écriture de `.batch_locks.json`
      en boucle serrée → `.batch_locks.json` reste un JSON valide en fin de
      run (pas de troncature/écrasement silencieux).

## 🖱️ Voir aussi crew/TESTS/DEV/batch-lock-hardening.md

Le scénario multi-session réel (deux vraies sessions Claude Code) n'est pas
scriptable depuis une seule session IA — checklist séparée côté DEV.

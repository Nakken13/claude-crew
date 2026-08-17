# Rename organized → claude-crew

Validation du rename `organized/` → `crew/` (repo + template global). Tous
les items sont exécutables par l'IA seule (🤖 auto / 🔍 commande directe).

- [x] 🔍 `cd "A:/projets_perso/organized" && grep -rn -E "organized|orga_hook|ORGA\b" .`
      ne retourne que des mentions attendues : fichiers de tâche/changelog
      historisant le rename, les URLs GitHub conservées dans `README.md`
      (`github.com/Nakken13/organized`), un diff d'archive figé sous
      `.superpowers/sdd/` (record historique d'une review passée, à ne pas
      toucher), et `crew/CLAUDE_CONTEXT/.task_state.json` (snapshot
      auto-régénéré par le hook, non versionné). Vérifié le 2026-08-17.
- [x] 🔍 Même grep sur `C:\Users\nahel\.claude\templates\project-scaffold\`
      ne retourne aucune occurrence de `organized|orga_hook|ORGA|orga-`.
      Vérifié le 2026-08-17.
- [x] 🤖 `python -m py_compile crew/crew_hook.py crew/spec_to_task_hook.py`
      (et l'équivalent dans le template) passe sans erreur. Vérifié le
      2026-08-17.
- [x] 🔍 `.claude/settings.json` : les commandes de hooks pointent vers des
      fichiers existants (`crew/crew_hook.py`, `crew/spec_to_task_hook.py`)
      dans le repo et dans le template. Vérifié le 2026-08-17.
- [x] 🤖 Déclencher un tour normal (Stop hook) et vérifier que
      `crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md` et les `INDEX.md` de
      `crew/*/` se régénèrent sans erreur (pas de traceback en stderr).
      Exécuté manuellement (`echo '{}' | python crew/crew_hook.py`), exit 0,
      `.task_state.json` correctement régénéré. Seul warning stderr :
      `[batch] CLAUDE_BATCH.md reference une tache inexistante : CLAUDE.md`
      — faux positif préexistant de `check_batches()` (regex matche toute
      mention `` `X.md` `` en prose, pas seulement les slugs de tâche), non
      lié au rename, hors périmètre de cette tâche.
- [x] 🔍 Les 5 skills `.claude/skills/crew-{init,new-task,close-task,status,start}`
      existent (repo et template) avec un `name:` frontmatter cohérent
      (`crew-*`, pas `organized-*`/`orga-*`). Vérifié le 2026-08-17.

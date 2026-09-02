# crew-dashboard

Validation du dashboard web local (`scripts/dashboard/server.py` + `static/`)
sur l'état `crew/` — voir `docs/superpowers/specs/2026-09-02-crew-dashboard-design.md`.

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 `.dashboard-venv/Scripts/python.exe -m pytest scripts/dashboard/test_server.py -q`
      (venv bootstrapé avec `requirements.txt` + `requirements-dev.txt`) —
      11/11 verts, dépôt git temporaire réel (pas de mock).
- [ ] 🔍 `diff skills/crew-dashboard/SKILL.md .claude/skills/crew-dashboard/SKILL.md`
      — vide (copies packagées synchronisées).
- [ ] 🔍 `git check-ignore -v .dashboard-venv` — confirmé ignoré par `.gitignore`.
- [ ] 🤖 (playwright, ou `claude-in-chrome` en ponctuel) — lancer le serveur
      (`server.py` depuis la racine du repo), charger `http://127.0.0.1:8943/`,
      vérifier que les 3 panneaux (Tasks/Batches/Sessions) rendent sans
      erreur console et que la ligne Sessions affiche bien
      `worktree: ... · branche: ...`.
- [ ] 🤖 Scénario bout-en-bout sur un dépôt de test jetable (jamais ce repo
      réel) : `POST /api/tasks/{slug}/move {"to":"CURRENT_TASKS"}` sur une
      tâche TODO → vérifier que `crew_lock.json` gagne une entrée
      `dashboard-ui` avec ce slug dans `tasks`, que `git mv` a bien eu lieu,
      puis `move {"to":"TODO"}` → vérifier que l'entrée `dashboard-ui`
      disparaît (ou son `tasks` se vide).
- [ ] 🔍 `POST /api/tasks/{slug}/move` vers `CURRENT_TASKS` alors qu'un
      voisin de batch est verrouillé par une autre session → 409 avec le
      détail du conflit, aucun `git mv` effectué.
- [ ] 🔍 `POST /api/sessions/{id}/purge` sur une session existante → 200,
      entrée retirée de `crew_lock.json` ; sur un id inconnu → 404.

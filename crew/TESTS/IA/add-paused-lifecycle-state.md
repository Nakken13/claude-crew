# add-paused-lifecycle-state

Validation du nouvel état de cycle de vie `crew/PAUSED/` (tâche démarrée,
bloquée sur une validation visuelle/dev, cf. `CLAUDE.md` § 2bis) et de son
câblage dans `crew/crew_hook.py` / `scripts/crew_hook.py`.

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py -q` — suite complète verte
      (25 tests, dont les 3 nouveaux sur PAUSED : `test_pause_move_not_reported_finished_keeps_lock`,
      `test_resumed_task_relabeled_and_rechecked_for_batch_collision`,
      `test_dup_paused_and_current_tasks_blocks`).
- [ ] 🔍 `diff crew/crew_hook.py scripts/crew_hook.py` — seul diff attendu :
      la ligne `ROOT = ...`.
- [ ] 🔍 `diff .claude/skills/crew-start/SKILL.md skills/crew-start/SKILL.md`
      et `diff .claude/skills/crew-status/SKILL.md skills/crew-status/SKILL.md`
      — vide dans les deux cas (copies packagées synchronisées).
- [ ] 🔍 Scénario bout-en-bout : créer une tâche jetable dans un dépôt de
      test, la démarrer (`crew/CURRENT_TASKS/`), la déplacer vers
      `crew/PAUSED/` (`git mv`), invoquer le hook Stop (`crew_hook.py`) et
      vérifier via `crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md` que l'entrée
      générée est `⏸️ mise en pause` (pas `✅ terminée`), puis la remettre en
      `crew/CURRENT_TASKS/` et vérifier l'entrée `▶️ reprise (post-pause)`.
- [ ] 🔍 Vérifier que `crew/PAUSED/INDEX.md` est bien régénéré (titre +
      intro, liste des tâches) après un tour Stop avec au moins un fichier
      dans `crew/PAUSED/`.

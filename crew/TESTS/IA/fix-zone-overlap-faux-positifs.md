# fix-zone-overlap-faux-positifs

Validation : `check_zone_overlaps` ne signale plus de chevauchement entre batchs
dont les tâches sont seulement en `crew/TODO/`, et ne bloque plus une session
étrangère à la collision. Voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md` (commit `13741dd`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py scripts/dashboard/test_server.py -q`
      → tout vert, dont `test_zone_overlap_*`, `test_in_progress_task_slugs_ignores_expired_session_lock`,
      `test_check_zone_overlaps_observer_view_blocks_cross_session`,
      `test_state_batch_with_only_todo_tasks_is_not_active`
- [ ] 🔍 Projet cible voyageo (après `/crew-update` ou mise à jour du plugin) :
      un tour Stop dans le checkout principal n'émet plus de `[zone]` entre
      « Batch — Perf ouverture workspace voyage » et « Batch — Plan : cards… »
      (tous deux ⏳ pas démarré)
- [ ] 🔍 time2cook : session sur Batch G (worktree) → un Stop dans le principal
      ne bloque pas une autre session non impliquée
- [ ] 🔍 Dashboard (`/crew-dashboard`) : un batch TODO-only affiche `active: false` ;
      une session > 6h ne rend plus son batch actif

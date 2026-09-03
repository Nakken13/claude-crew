# corriger-purge-batch-clos

Validation du fix de wording "barrer, jamais supprimer" pour la clôture de
tâche dans `crew/CLAUDE_BATCH.md` (`CLAUDE.md`, `template/CLAUDE.md`,
`.claude/skills/crew-close-task/SKILL.md`, `skills/crew-close-task/SKILL.md`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 Grep les 4 fichiers pour confirmer qu'aucun ne dit encore "retirer
      la tâche de sa ligne"/"supprimer la ligne" sans mention explicite de
      barrer (`~~slug.md~~`).
- [ ] 🔍 Rejouer la simulation `prune_closed_batches` (texte synthétique
      avec un batch entièrement barré, un batch mixte, un batch placeholder
      à 0 tâche référencée) et vérifier que seul le batch entièrement barré
      est purgé — script déjà exécuté en session, à rejouer pour non-
      régression après tout futur changement de `crew/crew_hook.py`.
- [ ] 🤖 Clore une tâche de test via `/crew-close-task` (scénario réel),
      vérifier que sa ligne dans `crew/CLAUDE_BATCH.md` est bien barrée
      (`~~`slug.md`~~`) et non supprimée.
- [ ] 🔍 Vérifier que `crew/CLAUDE_BATCH.md` de ce repo ne contient aucun
      header de batch orphelin (section sans aucune tâche référencée autre
      que les sections placeholder connues comme « À classer »).

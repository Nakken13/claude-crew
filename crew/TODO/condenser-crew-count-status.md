# Rendre /crew-count et /crew-status plus concis

## Contexte

Les skills `claude-crew:crew-count` et `claude-crew:crew-status` produisent
une sortie trop verbeuse pour des rapports censés être lecture-seule et
rapides à consulter. Objectif : resserrer le format de sortie (moins de
texte, plus condensé, type tableau/bullet compact) en gardant toute l'info
utile.

Pour `crew-count` : batchs déjà actifs / lançables maintenant / exclus pour
chevauchement de zone.

Pour `crew-status` : batchs actifs + zones (avec chevauchements), tâches
`CURRENT_TASKS/` avec % d'actions cochées, tests `crew/TESTS/IA/` non cochés,
tâches TODO non catégorisées dans `CLAUDE_BATCH.md`, placeholders `<...>`
restants.

## Actions

- [ ] Relire le format de sortie actuel de `crew-count` et `crew-status`
      (exemples réels sur ce projet, pas hypothétiques)
- [ ] Définir un format condensé cible (ex. une ligne par batch,
      symboles/emoji plutôt que phrases, pas de répétition d'explication à
      chaque run)
- [ ] Appliquer le nouveau format à `.claude/skills/crew-count/SKILL.md`
- [ ] Appliquer le nouveau format à `.claude/skills/crew-status/SKILL.md`
- [ ] Vérifier que l'info utile reste présente malgré la compression :
      chevauchements de zone, % d'actions cochées par tâche courante, tests
      IA non cochés, tâches TODO non catégorisées, placeholders `<...>`
      restants
- [ ] Faire tourner `/crew-count` et `/crew-status` sur ce projet après
      modification pour comparer avant/après et valider la lisibilité

## Zone d'impact

`.claude/skills/crew-count/SKILL.md`, `.claude/skills/crew-status/SKILL.md`
uniquement.

**Chevauchement connu** avec la tâche `reduire-tokens-subagents.md` sur ces
deux mêmes fichiers (cette tâche-là touche aussi leurs prompts de dispatch) —
même batch, cette tâche passe en second (format de sortie), après le trim des
prompts de dispatch.

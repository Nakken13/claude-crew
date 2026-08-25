# crew-count-batches

Validation de la skill `/crew-count` (`.claude/skills/crew-count/SKILL.md`) —
compte lecture seule des batchs `crew/CLAUDE_BATCH.md` lançables en
parallèle maintenant.

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 Invoquer `/crew-count` sur l'état réel du repo, comparer le chiffre
      annoncé à un comptage manuel de `crew/CLAUDE_BATCH.md` +
      `crew/CURRENT_TASKS/` (batchs hors « À classer », hors placeholder
      `<...>`, hors tâches barrées `~~slug.md~~`) — doivent correspondre
      exactement.
- [ ] 🔍 Scénario "batch actif" : avec un batch ayant ≥1 tâche déjà en
      `crew/CURRENT_TASKS/`, vérifier qu'il apparaît dans la section
      "batchs déjà actifs" avec le même niveau de détail (nom/Zone/nb
      tâches) que la liste des lançables, et n'est pas compté dans le
      chiffre de parallélisme disponible.
- [ ] 🔍 Scénario "chevauchement de zone" : créer temporairement (dans une
      copie du fichier, ou un scénario en mémoire) deux batchs avec des
      `Zone :` qui se recoupent, vérifier que `/crew-count` les exclut tous
      les deux du compte "sûr" et signale nommément le chevauchement
      (chemins en commun) plutôt que de les compter.
- [ ] 🔍 Scénario "placeholder non résolu" : vérifier qu'un batch au format
      gabarit initial (`Zone : <fichiers/modules>`, `<slug>.md`) est ignoré
      et signalé séparément plutôt que compté comme lançable — cas déjà
      couvert par `Batch A` dans l'état actuel de `crew/CLAUDE_BATCH.md` au
      moment de l'écriture.
- [ ] 🔍 Scénario "aucun batch lançable" : sur l'état actuel du repo (1 seul
      batch non vide, `plugin-packaging`, déjà actif), vérifier que
      `/crew-count` répond bien `0` explicitement (pas de silence) avec la
      raison ("tout est actif").

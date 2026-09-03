# condenser-crew-count-status

Validation du format de sortie condensé de `/crew-count` et `/crew-status`
(`.claude/skills/crew-count/SKILL.md`, `.claude/skills/crew-status/SKILL.md`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 Invoquer `/crew-status` sur l'état réel du repo, vérifier que la
      sortie suit le gabarit "Format de sortie" (sections emoji, une ligne
      par item, pas de paragraphe explicatif répété) plutôt que l'ancien
      format prose.
- [ ] 🔍 Invoquer `/crew-count` sur l'état réel du repo, même vérification
      de gabarit (🚀/🟢/⛔/🚧/📋).
- [ ] 🔍 Vérifier qu'aucune info requise n'a disparu par rapport à l'ancien
      format : chevauchements de zone (`⚠️ Chevauchements`), ratio d'actions
      cochées par tâche `CURRENT_TASKS` (`⏳ En cours`), fichiers
      `crew/TESTS/IA/*.md` non cochés (`📝`), tâches TODO non catégorisées
      (`🗑️`), placeholders `<...>` restants (`⚠️ Bootstrap`), batchs à
      placeholder non résolu (`🚧` côté `crew-count`).
- [ ] 🔍 Scénario "deux batchs actifs qui se chevauchent" : vérifier que le
      chevauchement apparaît une seule fois dans `⚠️ Chevauchements` (pas
      dupliqué sous chaque batch).
- [ ] 🔍 Scénario "tâche en pause" (`crew/PAUSED/<slug>.md`) : vérifier que
      la ligne `⏸️ En pause` reste générique ("bloqué, validation dev en
      attente") sans lecture/paraphrase du contenu du fichier.

# reduire-tokens-subagents

Validation des changements visant à réduire la consommation de tokens des
dispatches de personas/subagents crew (`CLAUDE.md` § Personas / § Batching /
§ Efficience de contexte, `crew-new-task`/`crew-start` SKILL.md, 4 personas).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 Diff des 3 paires de fichiers mirroir (`.claude/agents/*.md` vs
      `agents/*.md` ; `.claude/skills/crew-start/SKILL.md` vs
      `skills/crew-start/SKILL.md` ; `.claude/skills/crew-new-task/SKILL.md`
      vs `skills/crew-new-task/SKILL.md`) — doivent rester identiques après
      toute future édition (pas de divergence packagée/dev).
- [ ] 🔍 Grep `CLAUDE.md` pour confirmer une seule occurrence canonique de la
      condition « `crew/CURRENT_TASKS/` et `crew/PAUSED/` vides » (§
      Batching), et que § Personas + `crew-start/SKILL.md` s'y réfèrent sans
      la réécrire intégralement (pas de retour de la duplication à 3
      endroits corrigée par cette tâche).
- [ ] 🤖 Lors du prochain `/crew-start` en Cas B avec `crew/CURRENT_TASKS/`
      et `crew/PAUSED/` vides : vérifier que le dispatch `Agent({subagent_
      type: "manager"})` de l'étape 5B est bien sauté (pas d'appel), et que
      la tâche démarre quand même correctement (git mv effectif, INDEX.md à
      jour, pas de faux négatif de sécurité — aucun autre batch ne devient
      actif entre-temps).
- [ ] 🤖 Lors du prochain `/crew-start` en Cas B avec ≥1 batch déjà actif :
      vérifier que le dispatch `manager` a toujours lieu (la vérification
      directe reste bornée au cas trivial, pas de sur-optimisation qui
      sauterait aussi les cas où l'anti-collision est réellement nécessaire).

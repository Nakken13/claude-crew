# commit-implementation-crew-close-task

Validation de la nouvelle étape 4 (commit d'implémentation) du protocole
`crew-close-task` (`.claude/skills/crew-close-task/SKILL.md` + copie
packagée `skills/crew-close-task/SKILL.md`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 Diff des deux copies (`.claude/skills/crew-close-task/SKILL.md` vs
      `skills/crew-close-task/SKILL.md`) — doivent rester identiques après
      toute future édition.
- [ ] 🔍 Relire la numérotation des étapes (1 à 7) dans les deux fichiers :
      pas de doublon, pas de référence obsolète à un ancien numéro d'étape
      (ex. « point 4 »/« point 5 » cités en interne doivent bien pointer sur
      le commit d'implémentation / le bookkeeping respectivement).
- [ ] 🤖 Lors du prochain `/crew-close-task` réel sur une tâche qui a créé au
      moins un fichier nouveau (non tracké) : vérifier que le `git add --
      <fichiers>` scopé est bien fait avant le `git commit --` (pas de
      fichier nouveau silencieusement absent du commit d'implémentation).
- [ ] 🤖 Lors du prochain `/crew-close-task` : vérifier que le commit
      d'implémentation ne contient aucun des chemins bookkeeping listés au
      point 4 (`crew/CURRENT_TASKS/<slug>.md`, `HISTORIQUE.md`, `TESTS/`,
      `CLAUDE_BATCH.md`, `INDEX.md`) — ces chemins doivent apparaître dans le
      commit bookkeeping séparé (point 5), pas dans celui-ci.
- [ ] 🤖 Lors du prochain `/crew-close-task` sur une tâche purement
      bookkeeping/doc crew : vérifier que le no-op est bien signalé
      explicitement dans le rapport final, pas silencieusement omis.

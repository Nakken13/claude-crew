# ancrer-crew-racine-repo

Validation du fix "ancrage racine obligatoire" pour tous les chemins
`crew/...` (`.claude/agents/manager.md`, les 6 skills `crew-*`, leurs 3
copies packagées, `CLAUDE.md` § Guides AGENTS.md segmentés).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 Rejouer la reproduction : depuis un cwd de sous-dossier (`frontend/`
      ou équivalent), vérifier qu'un chemin relatif `crew/TODO/test.md`
      résoudrait sous ce sous-dossier plutôt qu'à la racine — confirme que
      le risque existe toujours sans ancrage explicite (le fix est de la
      prose, pas un blocage mécanique).
- [ ] 🔍 Grep les 10 fichiers concernés (`manager.md`, 6 `.claude/skills/
      crew-*/SKILL.md`, 3 copies `skills/crew-{close-task,new-task,
      start}/SKILL.md`) pour confirmer la présence du paragraphe "Ancrage
      racine obligatoire".
- [ ] 🔍 Vérifier que les copies packagées `skills/crew-close-task`,
      `skills/crew-new-task`, `skills/crew-start` sont toujours identiques
      à leurs originaux `.claude/skills/` (non-régression du drift corrigé
      par cette tâche).
- [ ] 🔍 Vérifier qu'aucun `crew/` fantôme n'existe dans un sous-dossier de
      ce repo (hors `template/crew/`, squelette légitime du scaffold).
- [ ] 🤖 Lancer `/crew-start`/`/crew-new-task` depuis un cwd volontairement
      placé dans un sous-dossier (scénario réel) et vérifier qu'aucun
      `crew/` fantôme n'apparaît — validation bout-en-bout du fix.

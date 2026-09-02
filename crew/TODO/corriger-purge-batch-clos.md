# Corriger la purge des batchs clos dans CLAUDE_BATCH.md

## Contexte

Sur un autre projet (voyageo) utilisant le même scaffold, `crew/CLAUDE_BATCH.md`
a grossi à >1000 lignes malgré la règle "Nettoyage automatique" documentée
dans `CLAUDE.md` § Batching (un batch dont toutes les tâches sont barrées
`~~slug.md~~` doit être retiré automatiquement au tour suivant).

**Root cause déjà identifiée dans ce repo** (pas besoin de ré-investiguer) :
`.claude/skills/crew-close-task/SKILL.md` ligne 34 dit "Retirer la tâche de
sa ligne dans `crew/CLAUDE_BATCH.md`" — c'est-à-dire **supprimer** la ligne.
Mais `prune_closed_batches()` dans `scripts/crew_hook.py` (et sa copie
déployée `crew/crew_hook.py`) détecte un batch clos en cherchant des tâches
**barrées** (`~~slug.md~~`), et laisse explicitement intactes les sections à
0 tâche référencée (pour ne pas supprimer un batch placeholder jamais
démarré). Résultat : un batch réellement clos finit avec un header vide
(toutes ses lignes de tâches supprimées une à une) au lieu d'avoir ses
tâches barrées → il ne matche jamais la condition de purge → il reste
indéfiniment dans le fichier, indistinguable d'un placeholder jamais
démarré.

**Fix probable** (à valider par la tâche, pas à trancher ici) : faire barrer
(`~~...~~`) la ligne de tâche dans crew-close-task au lieu de la supprimer,
pour rester cohérent avec ce que `prune_closed_batches` attend déjà — c'est
le fix minimal qui ne touche pas à la logique hook existante.

Alternative écartée a priori : changer `prune_closed_batches` pour aussi
purger les sections à 0 tâche référencée — écartée car ça casserait la
distinction avec les batchs placeholder jamais démarrés (section "À
classer" ou batch créé par anticipation sans tâche encore rattachée).

## Actions

- [ ] Confirmer le bug en reproduisant localement (clore une tâche via
      crew-close-task, vérifier que sa ligne est supprimée et non barrée
      dans `CLAUDE_BATCH.md`)
- [ ] Corriger crew-close-task (`.claude/skills/crew-close-task/SKILL.md` +
      toute copie packagée du plugin, notamment `skills/crew-close-task/SKILL.md`)
      pour barrer (`~~slug.md~~`) la ligne au lieu de la supprimer
- [ ] Vérifier que `prune_closed_batches` (`scripts/crew_hook.py` et
      `crew/crew_hook.py`) purge bien le batch au tour suivant une fois
      toutes ses tâches barrées
- [ ] Vérifier/adapter `CLAUDE.md` § Batching si le wording décrit mal le
      comportement réel
- [ ] Nettoyer manuellement `crew/CLAUDE_BATCH.md` de ce repo si des headers
      vides orphelins y trainent déjà (audit rapide)
- [ ] Documenter dans `HISTORIQUE` si pertinent pour que les projets déjà
      déployés (voyageo) sachent qu'il faut mettre à jour leur copie du
      plugin/scaffold

## Zone d'impact

`.claude/skills/crew-close-task/SKILL.md`, `skills/crew-close-task/SKILL.md`
(copie packagée plugin), `scripts/crew_hook.py`, `crew/crew_hook.py`,
`crew/CLAUDE_BATCH.md` (nettoyage ponctuel), `CLAUDE.md` § Batching.

**Chevauchement identifié** avec la tâche `reduire-tokens-subagents.md` du
batch "Crew subagents & reporting skills" : sa zone déclarée inclut déjà
`.claude/skills/crew-close-task/SKILL.md` (trim des prompts de dispatch).
Cette tâche-ci touche une autre section du même fichier (le wording de
l'étape 4, "retirer la tâche de sa ligne"), mais c'est le même fichier —
donc même batch pour respecter l'invariant de disjonction, même si les deux
tâches éditent des paragraphes différents et n'ont pas de dépendance
fonctionnelle stricte entre elles.

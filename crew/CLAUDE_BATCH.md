# Batching — workstreams parallèles

Un batch = un Claude. Voir § Batching dans `CLAUDE.md` racine pour les règles
(zone d'impact, invariant de disjonction entre batchs actifs).

## Batch — Crew subagents & reporting skills

Zone : `.claude/agents/*.md` ; `.claude/skills/crew-new-task/SKILL.md`,
`.claude/skills/crew-close-task/SKILL.md` (aussi copie packagée
`skills/crew-close-task/SKILL.md`), `.claude/skills/crew-start/SKILL.md`
(prompts de dispatch) ; `.claude/skills/crew-status/SKILL.md`,
`.claude/skills/crew-count/SKILL.md` (dispatch **et** format de sortie) ;
`scripts/crew_hook.py`, `crew/crew_hook.py`, `crew/CLAUDE_BATCH.md`
(nettoyage ponctuel, tâche 3 uniquement) ; `.claude/skills/crew-init/SKILL.md`
(tâche 4 uniquement) ; `CLAUDE.md` § Personas / § Efficience de contexte /
§ Batching / § Guides AGENTS.md segmentés / § Gestion des tâches.

Tâches (ordre à respecter — toutes touchent tout ou partie de
`manager.md` / `crew-close-task` / `crew-status` / `crew-count`
`SKILL.md`, séquencées pour éviter un conflit d'édition) :
1. ~~`crew/TODO/reduire-tokens-subagents.md`~~ — trim des prompts de dispatch,
   y compris dans crew-status/crew-count. Clôturée 2026-09-02, cf.
   `crew/CLAUDE_CONTEXT/HISTORIQUE.md`.
2. `crew/TODO/condenser-crew-count-status.md` — condense le format de
   sortie de crew-status/crew-count, une fois (1) fait sur ces fichiers.
3. `crew/TODO/corriger-purge-batch-clos.md` — fait barrer (au lieu de
   supprimer) la ligne de tâche dans `crew-close-task/SKILL.md` lors de la
   clôture, pour que `prune_closed_batches` purge correctement les batchs
   clos. Pas de dépendance fonctionnelle avec (1)/(2), mais touche le même
   fichier `.claude/skills/crew-close-task/SKILL.md` (zone déjà déclarée par
   la tâche 1) — rattachée à ce batch pour respecter l'invariant de
   disjonction plutôt que créer un nouveau batch qui collisionnerait dessus.
4. `crew/TODO/ancrer-crew-racine-repo.md` — ancre tous les chemins `crew/...`
   à la racine du repo (bug crew/ fantôme créé dans un sous-dossier type
   frontend/backend quand le cwd n'est pas la racine) dans `manager.md` et
   les 6 skills `crew-*` (`crew-new-task`, `crew-close-task`, `crew-init`,
   `crew-status`, `crew-count`, `crew-start`). Pas de dépendance
   fonctionnelle avec (1)/(2)/(3), mais touche les mêmes fichiers
   (`manager.md`, `crew-status/SKILL.md`, `crew-count/SKILL.md`,
   `crew-close-task/SKILL.md`, zone déjà déclarée) — rattachée à ce batch
   pour respecter l'invariant de disjonction, séquencée en dernier avant (5).
5. `crew/CURRENT_TASKS/commit-implementation-crew-close-task.md` — ajoute
   une étape explicite de commit de l'implémentation (fichiers hors
   bookkeeping crew/) dans `crew-close-task/SKILL.md`, entre les étapes
   "passes obligatoires" et "bookkeeping" existantes. Pas de dépendance
   fonctionnelle avec (1)/(2)/(3)/(4), mais touche le même fichier
   `.claude/skills/crew-close-task/SKILL.md` (et sa copie packagée
   `skills/crew-close-task/SKILL.md`, zone déjà déclarée) — rattachée à ce
   batch pour respecter l'invariant de disjonction, séquencée en dernier
   pour éviter un conflit d'édition si plusieurs tâches de ce batch sont
   traitées dans la même session. Démarrée directement en
   `crew/CURRENT_TASKS/` (demande explicite de démarrage immédiat, aucun
   batch actif au moment du découpage — pas de collision).

Note : (1) et (2) demandées initialement comme deux batchs séparés ("zones
distinctes"), mais leurs zones déclarées se chevauchent réellement sur
`crew-status/SKILL.md` et `crew-count/SKILL.md` (tâche 1 touche leurs prompts
de dispatch, tâche 2 leur format de sortie) — regroupées ici pour respecter
l'invariant de disjonction entre batchs actifs plutôt que créer une collision
potentielle si les deux étaient démarrées en parallèle. (3) et (4) rattachées
selon le même raisonnement (chevauchement de fichiers, pas de zone
indépendante viable).


# Ajouter un commit d'implémentation explicite à `crew-close-task`

## Contexte

`crew/crew_hook.py` (`_closure_commit_scope` / `auto_commit_closure`,
lignes ~1059-1160) fait déjà un commit auto de clôture, mais **scopé
uniquement au bookkeeping crew/** : le fichier `CURRENT_TASKS/<slug>.md`
supprimé, `HISTORIQUE.md`, les tests sortis (`TESTS/IA`, `TESTS/DEV`),
`CLAUDE_BATCH.md`, `BATCH_LOCKS.md`, `CHANGELOG_TACHES.md`, tous les
`INDEX.md`. Il ne committe **jamais** les fichiers d'implémentation réels
de la tâche (code, doc hors crew/, etc.) — ce n'est ni son rôle ni son
scope actuel, et ce n'est **pas** ce que cette tâche change.

**Décision déjà tranchée par `architect`, ne pas revenir dessus** : ne pas
automatiser le commit d'implémentation dans le hook Stop
(`crew/crew_hook.py`). Risque déjà vécu cette session : une automatisation
basée sur la section libre `## Zone d'impact` d'un fichier de tâche
pourrait embarquer dans le commit des edits d'un **fichier partagé** (ex.
`CLAUDE.md`) appartenant en réalité à une **autre tâche** déjà historisée
mais pas encore committée — l'incident "ProjetA" documenté dans
`crew/CLAUDE_CONTEXT/HISTORIQUE.md`, à la granularité fichier au lieu de
la granularité index/staged que `auto_commit_closure` maîtrise déjà.

À la place : ajouter une **étape explicite** dans
`.claude/skills/crew-close-task/SKILL.md` (et sa copie packagée
`skills/crew-close-task/SKILL.md`), entre l'étape 3 (passes obligatoires
`requesting-code-review`/`simplify`) et l'étape 4 (bookkeeping) actuelles :
la session qui clôture fait un `git status`/review manuel des fichiers
**réellement touchés par sa propre tâche** (celle en cours de clôture, pas
une autre tâche en parallèle), puis un `git commit -- <ces fichiers>`
scopé à ces fichiers — jamais un `git commit` nu, jamais `git add -A`,
jamais de push. Même rigueur/non-optionnalité que les passes
`requesting-code-review`/`simplify` déjà en place.

## Actions

- [ ] Dans `.claude/skills/crew-close-task/SKILL.md`, insérer une nouvelle
      étape (numérotée à sa place, entre l'étape 3 actuelle et l'étape 4
      actuelle — renuméroter les étapes suivantes en conséquence) décrivant :
      `git status` / review manuel des fichiers réellement modifiés par la
      tâche en cours de clôture (pas une autre tâche active en parallèle),
      puis `git commit -- <fichiers>` scopé à ces seuls fichiers.
- [ ] Préciser explicitement dans cette nouvelle étape : jamais `git commit`
      nu, jamais `git add -A`/`git add .`, jamais de push — même contrainte
      que le reste du protocole crew.
- [ ] Préciser explicitement que ce commit est **distinct et complémentaire**
      du commit auto de bookkeeping crew/ déjà fait par
      `crew/crew_hook.py::auto_commit_closure` à l'étape bookkeeping (qui ne
      touche que les chemins crew/ listés dans `_closure_commit_scope` —
      `CURRENT_TASKS/<slug>.md` supprimé, `HISTORIQUE.md`, `TESTS/`,
      `CLAUDE_BATCH.md`, `INDEX.md`) : ne pas dupliquer ce scope, ne pas le
      contredire, ne pas re-committer les mêmes chemins bookkeeping dans ce
      nouveau commit d'implémentation.
- [ ] Couvrir explicitement le cas où la tâche clôturée est purement
      bookkeeping/doc crew (aucun fichier d'implémentation touché hors
      crew/) : cette étape est alors un **no-op explicite documenté**
      ("rien à committer ici"), pas un skip silencieux ni une case ambiguë.
- [ ] Mettre à jour la section "Ce que ce skill ne fait pas" en fin de
      fichier avec une ligne dédiée (ex. ne jamais faire un `git commit` nu
      ou `git add -A` pour committer l'implémentation — toujours un commit
      scopé aux fichiers identifiés).
- [ ] Mettre à jour l'étape de rapport final (dernière étape du skill) pour
      inclure, en plus de ce qui est déjà rapporté (historisation, tests,
      batch, sort du worktree), les fichiers/commit de l'implémentation
      committés à cette nouvelle étape.
- [ ] Appliquer un wording strictement identique dans
      `skills/crew-close-task/SKILL.md` (copie packagée) — les deux
      fichiers doivent rester synchronisés comme toutes les paires
      `.claude/` vs racine de ce projet.
- [ ] Relire l'ensemble du fichier une fois l'étape insérée pour vérifier
      que la numérotation des étapes suivantes (bookkeeping, intégration
      worktree, rapport) est cohérente dans les deux fichiers.

## Ce que cette tâche ne fait PAS

- Ne touche pas à `crew/crew_hook.py` ni `scripts/crew_hook.py` (hors
  scope, décision `architect` déjà actée ci-dessus).
- Ne change rien au comportement de `auto_commit_closure`/
  `_closure_commit_scope` — uniquement de la documentation de protocole
  dans le skill.

## Zone d'impact

`.claude/skills/crew-close-task/SKILL.md`, `skills/crew-close-task/SKILL.md`
(copie packagée).

**Chevauchement identifié** avec le batch "Crew subagents & reporting
skills" (`crew/CLAUDE_BATCH.md`) : ce fichier est déjà dans la zone
déclarée de ce batch (tâches 1/3/4, dont `corriger-purge-batch-clos.md` en
`crew/TODO/` qui touche l'étape "retirer la tâche de sa ligne" du même
fichier, et `ancrer-crew-racine-repo.md` qui ancre les chemins dans les 6
skills `crew-*` dont celui-ci). Contenu indépendant (aucune dépendance
fonctionnelle stricte — cette tâche ajoute une étape de commit, les autres
touchent le wording de purge de batch et l'ancrage de chemins), mais même
fichier `SKILL.md` → rattachée à ce batch pour respecter l'invariant de
disjonction plutôt que créer un nouveau batch qui collisionnerait dessus.
Séquencée en dernier (après 1/2/3/4) pour éviter un conflit d'édition si
plusieurs de ces tâches sont un jour traitées dans la même session.

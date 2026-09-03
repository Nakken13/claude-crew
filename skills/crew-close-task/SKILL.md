---
name: crew-close-task
description: Clôture une tâche crew terminée (crew/CURRENT_TASKS/<slug>.md) — vérifie que toutes les actions sont cochées, applique les passes obligatoires avant closing (requesting-code-review, simplify + modularité), historise dans CLAUDE_CONTEXT/HISTORIQUE.md, sort les tests dans TESTS/IA et/ou TESTS/DEV, retire la tâche de son batch. Trigger — "/crew-close-task", "cette tâche est finie", "clôture la tâche", "code fini, on ferme".
---

Exécute le protocole défini dans `CLAUDE.md` § "Gestion des tâches" (point
3) — ne pas clore une tâche en sautant ces étapes, même perçue comme petite
(obligation de modularité, cf. `CLAUDE.md` § "Modularité du code" /
`crew/CLAUDE_CONTEXT/AGENTS.md` si ce projet y documente des anti-patterns
précis).

## Étapes

1. Identifier le fichier `crew/CURRENT_TASKS/<slug>.md` concerné (demander
   lequel si plusieurs tâches sont actives et que l'utilisateur n'a pas
   précisé).
2. Vérifier que **toutes** les actions `- [ ]` du fichier sont cochées
   `- [x]`. Si non → **ne pas continuer** : lister les actions restantes et
   s'arrêter là.
3. Passes obligatoires avant closing (pas optionnelles, pas de raccourci
   même sur une tâche perçue comme petite) :
   - Skill `requesting-code-review` sur le code touché par la tâche.
   - Skill `simplify` sur le même périmètre — couvre réutilisation,
     simplification, efficacité **et** modularité (pas de fichier
     fourre-tout, pas de logique dupliquée à 2+ endroits sans extraction).
4. **Commit de l'implémentation**, une fois les passes du point 3 faites et
   les retours appliqués : `git status` pour identifier les fichiers
   réellement modifiés par **cette tâche** (celle en cours de clôture — pas
   une autre tâche qui traînerait en parallèle dans le même checkout).
   Croiser cette liste avec la `Zone :` déjà déclarée pour cette tâche dans
   `crew/CLAUDE_BATCH.md` : un fichier hors de cette zone ne doit jamais
   être ajouté sans vérification — en cas de doute, demander plutôt que
   d'inclure silencieusement. Puis `git add -- <ces fichiers>` et `git
   commit -- <ces fichiers>` (le `git add` scopé est nécessaire pour les
   fichiers nouvellement créés, que `git commit --` seul ne stage pas ;
   jamais `-A`/`git add .`, jamais `git commit` nu, jamais de push).
   Distinct et complémentaire du commit auto de bookkeeping crew/ (point 5
   ci-dessous, `crew/crew_hook.py::auto_commit_closure`) : ne pas
   recommitter ici les chemins bookkeeping (`crew/CURRENT_TASKS/<slug>.md`,
   `HISTORIQUE.md`, `TESTS/`, `CLAUDE_BATCH.md`, `INDEX.md`) déjà gérés par
   ce mécanisme séparé. Tâche purement bookkeeping/doc crew (aucun fichier
   d'implémentation touché hors crew/) → no-op explicite : le dire (« rien
   à committer ici »).
5. Une fois le commit d'implémentation fait (ou son no-op constaté) :
   - Supprimer `crew/CURRENT_TASKS/<slug>.md`.
   - Ajouter une entrée dans `crew/CLAUDE_CONTEXT/HISTORIQUE.md` : quoi,
     quand, fichiers/commits clés.
   - Créer `crew/TESTS/IA/<slug>.md` et/ou `crew/TESTS/DEV/<slug>.md` selon
     le critère de tri de `CLAUDE.md` (🤖/🔍 = l'IA peut dérouler seule ;
     🖱️ = action humaine réellement nécessaire). Ne pas cocher ces tests à
     la création — validation pour une session ultérieure.
   - Barrer la ligne de la tâche dans `crew/CLAUDE_BATCH.md` (`~~\`slug.md\`~~`,
     batch ou section « À classer ») — **ne jamais supprimer la ligne** :
     `prune_closed_batches` (`crew/crew_hook.py`) ne retire un batch que
     lorsque toutes ses tâches référencées sont barrées ; une ligne
     supprimée au lieu d'être barrée laisse un header de batch orphelin
     que la purge automatique ne détecte jamais.
6. **Intégration du worktree de batch**, si la session travaille depuis un
   worktree `../<nom-repo>-batch-<slug>/` sur la branche `crew/batch-<slug>`
   (isolation physique posée par `/crew-start`, cf.
   `docs/superpowers/specs/2026-08-22-worktree-batch-isolation-design.md`) :
   - Si **d'autres tâches du même batch** restent en `crew/CURRENT_TASKS/`
     (batch pas encore entièrement terminé) → ne pas toucher au worktree,
     il sert encore. S'arrêter là pour cette section.
   - Sinon (batch entièrement terminé) : `git rebase main` sur la branche
     `crew/batch-<slug>` (rebase strictement local — pas de `git fetch`,
     aucun remote n'est supposé exister).
     - Rebase propre → fusionner en fast-forward dans `main`, puis
       `git worktree remove ../<nom-repo>-batch-<slug>` et
       `git branch -d crew/batch-<slug>`. Revenir (`cd`) au checkout
       principal avant de continuer.
     - Conflit au rebase → `git rebase --abort`, garder le worktree et la
       branche intacts, lister les fichiers en conflit à l'utilisateur pour
       résolution manuelle. Ne pas tenter de retirer l'entrée session de
       `crew_lock.json` à la main : `crew/crew_hook.py` la nettoie déjà tout
       seul (Stop/SessionEnd) — le travail de code est fini même si
       l'intégration ne l'est pas encore.
7. Rapporter : fichiers/commit de l'implémentation (point 4, ou son no-op
   constaté), ce qui a été historisé, fichiers de tests créés (IA/DEV),
   batch mis à jour, et le sort du worktree de batch (conservé car batch pas
   fini / fusionné et supprimé / conflit laissé pour résolution manuelle).

## Ce que ce skill ne fait pas

- Ne coche jamais des actions à la place de l'utilisateur pour pouvoir clore
  plus vite — si des actions restent non cochées, il s'arrête et le dit.
- Ne saute jamais les passes `requesting-code-review`/`simplify`/modularité,
  quelle que soit la taille perçue de la tâche.
- Ne décide pas qu'un test va en `IA/` par défaut — applique le vrai critère
  (l'IA a-t-elle de quoi l'exécuter elle-même ?), pas une facilité.
- Ne supprime jamais un worktree/branche de batch tant qu'une autre tâche du
  même batch est encore en `crew/CURRENT_TASKS/`.
- Ne résout jamais un conflit de rebase automatiquement — l'abandonne
  proprement et le signale, ne discard jamais le travail du worktree.
- Ne committe jamais l'implémentation hors du scoping du point 4 (jamais
  `git commit` nu ou `git add -A`/`git add .`).

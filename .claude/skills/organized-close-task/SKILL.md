---
name: organized-close-task
description: Clôture une tâche organized terminée (organized/CURRENT_TASKS/<slug>.md) — vérifie que toutes les actions sont cochées, applique les passes obligatoires avant closing (requesting-code-review, simplify + modularité), historise dans CLAUDE_CONTEXT/HISTORIQUE.md, sort les tests dans TESTS/IA et/ou TESTS/DEV, retire la tâche de son batch. Trigger — "/organized-close-task", "cette tâche est finie", "clôture la tâche", "code fini, on ferme".
---

Exécute le protocole défini dans `CLAUDE.md` § "Gestion des tâches" (point
3) — ne pas clore une tâche en sautant ces étapes, même perçue comme petite
(obligation de modularité, cf. `CLAUDE.md` § "Modularité du code" /
`organized/CLAUDE_CONTEXT/AGENTS.md` si ce projet y documente des anti-patterns
précis).

## Étapes

1. Identifier le fichier `organized/CURRENT_TASKS/<slug>.md` concerné (demander
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
4. Une fois les passes faites et les retours appliqués :
   - Supprimer `organized/CURRENT_TASKS/<slug>.md`.
   - Ajouter une entrée dans `organized/CLAUDE_CONTEXT/HISTORIQUE.md` : quoi,
     quand, fichiers/commits clés.
   - Créer `organized/TESTS/IA/<slug>.md` et/ou `organized/TESTS/DEV/<slug>.md` selon
     le critère de tri de `CLAUDE.md` (🤖/🔍 = l'IA peut dérouler seule ;
     🖱️ = action humaine réellement nécessaire). Ne pas cocher ces tests à
     la création — validation pour une session ultérieure.
   - Retirer la tâche de sa ligne dans `organized/CLAUDE_BATCH.md` (batch ou
     section « À classer »).
5. Rapporter : ce qui a été historisé, fichiers de tests créés (IA/DEV),
   batch mis à jour.

## Ce que ce skill ne fait pas

- Ne coche jamais des actions à la place de l'utilisateur pour pouvoir clore
  plus vite — si des actions restent non cochées, il s'arrête et le dit.
- Ne saute jamais les passes `requesting-code-review`/`simplify`/modularité,
  quelle que soit la taille perçue de la tâche.
- Ne décide pas qu'un test va en `IA/` par défaut — applique le vrai critère
  (l'IA a-t-elle de quoi l'exécuter elle-même ?), pas une facilité.

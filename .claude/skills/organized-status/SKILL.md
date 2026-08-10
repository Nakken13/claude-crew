---
name: organized-status
description: Rapport lecture seule de l'état organized — batchs actifs et zones (chevauchements éventuels), tâches en cours (CURRENT_TASKS avec % d'actions cochées), tests organized/TESTS/IA non cochés, tâches TODO non catégorisées dans CLAUDE_BATCH.md, et placeholders <...> restants si le scaffold est encore en bootstrap. Trigger — "/organized-status", "où en est le projet", "état des batchs", "statut organized".
---

Skill lecture seule — ne modifie aucun fichier. Complète le hook `Stop`
(`organized/organized_hook.py`, sortie discrète en stderr) par une vue à la demande,
en session.

## Ce qu'il rapporte

1. **Batchs actifs** (`organized/CLAUDE_BATCH.md`) : liste des batchs ayant ≥1
   tâche en `organized/CURRENT_TASKS/`, leur `Zone :` déclarée, et tout
   chevauchement de zone détecté entre deux batchs actifs différents —
   invariant violé, à signaler explicitement, pas juste à lister en
   passant.
2. **Tâches en cours** (`organized/CURRENT_TASKS/*.md`) : pour chacune, ratio
   actions cochées / total.
3. **Tests IA non cochés** (`organized/TESTS/IA/*.md`) : fichiers avec au moins
   une case non cochée — ce qui reste à valider.
4. **Tâches TODO orphelines** : présentes dans `organized/TODO/` mais absentes de
   `organized/CLAUDE_BATCH.md` (ni batch, ni section « À classer »).
5. **Bootstrap** : si `check_placeholders.py` existe encore à la racine, le
   lancer et inclure son résultat — des placeholders `<...>` restants
   signifient que le scaffold n'est pas encore totalement initialisé
   (renvoyer vers `/organized-init`).

## Ce que ce skill ne fait pas

- N'écrit, ne déplace, ne coche aucun fichier — pur reporting.
- Ne remplace pas `/organized-new-task` ou `/organized-close-task` pour agir sur une
  tâche — sert seulement à avoir une vue avant de décider quoi faire.

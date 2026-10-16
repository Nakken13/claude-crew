---
name: crew-count
description: Rapport lecture seule — combien de batchs de CLAUDE_BATCH.md sont lançables en parallèle (actifs, lançables, exclus pour chevauchement). Trigger — "/crew-count", "combien de Claude en parallèle".
---

Lecture seule — ne modifie aucun fichier. Le calcul est fait par un script
déterministe ; ce skill ne fait que présenter son résultat.

1. Lancer (plugin : `scripts/crew_hook.py` du plugin ; clone manuel :
   `crew/crew_hook.py`) :

   ```bash
ROOT="$(git rev-parse --show-toplevel)"; HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" count
```

   Sortie JSON : `launchable_count`, `launchable[]` (`name`, `zone`, `remaining`,
   `task` = titre de session), `active[]`, `excluded[]`, `placeholders[]` et
   **`report`** : texte markdown déjà rendu (nombre exact + tableau
   titre/batch/zone + actifs/exclus en une ligne).

2. Répondre en affichant **`report` tel quel**, rien d'autre (pas de
   reformulation, pas de rappel des règles). Chaque titre de la colonne
   « Titre de session » est le slug de la tâche à donner au terminal
   (`/rename` ou premier message) ; `/crew-start` la reprend.

## Ce que ce skill ne fait pas

- N'écrit rien, ne démarre aucune tâche (décision à l'utilisateur ou
  `/crew-start`), ne recatégorise pas « À classer ».

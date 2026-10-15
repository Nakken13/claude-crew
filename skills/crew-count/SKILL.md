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

   Sortie JSON : `launchable_count`, `launchable[]`, `active[]`, `excluded[]`
   (avec `reason`), `placeholders[]`. Chaque batch : `name`, `zone`,
   `remaining`. Le script ignore déjà les tâches barrées (`~~…~~`), les
   batchs sans tâche restante, la section « À classer » (zone inconnue) et
   les placeholders de template (`<...>`), et vérifie la disjonction de
   zones actifs + lançables entre eux.

2. Répondre, dans cet ordre :
   - le **nombre** `launchable_count` en tête (`0` dit explicitement, avec la
     raison dominante : tout actif, tout clôturé ou tout en « À classer ») ;
   - les batchs lançables : nom, `Zone :`, tâches restantes ;
   - les batchs **déjà actifs** (informatif, hors du compte) ;
   - les **exclus** : nom + `reason` (batchs et chemins en commun) —
     avertissement explicite, jamais compté ;
   - `placeholders` non vide : « placeholder non résolu, ignoré ».

## Ce que ce skill ne fait pas

- N'écrit rien, ne démarre aucune tâche (décision à l'utilisateur ou
  `/crew-start`), ne recatégorise pas « À classer ».

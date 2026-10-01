# Moniteur de contexte : seuil fixe 150k et répétition stderr sans intervalle

Statut : 🟡 en cours — tâche : `crew/TODO/moniteur-contexte-seuil-fixe-stderr.md` (Batch A, cf. `crew/CLAUDE_BATCH.md`)

## Constat

`check_context_budget` (hook Stop) :

- Seuil fixe à 150k tokens, non scalé à la taille réelle de la fenêtre
  (200k vs 1M).
- Une fois le seuil dépassé, l'avertissement est émis sur stderr à **chaque**
  Stop, sans intervalle de répétition.
- Aucune détection de boucle (appels d'outils identiques répétés).

Comparaison ECC : seuil scalé (160k sur fenêtre 200k, 250k sur 1M),
répétition tous les 60k tokens seulement, détection « 5 derniers appels
d'outils identiques », `additionalContext` debouncé.

## Impact

- Mineur. Sur fenêtre 1M, l'alerte arrive beaucoup trop tôt et devient du
  bruit ; sur 200k, elle se répète à chaque tour une fois franchie, au moment
  précis où chaque token compte.
- Pas de signal sur une boucle d'agent, pourtant gros consommateur de tokens.

## Pistes

- Scaler le seuil à la fenêtre détectée (ratio plutôt que valeur absolue).
- Répéter l'alerte par palier (ex. tous les 60k) au lieu de chaque Stop.
- Détection simple de boucle sur les N derniers appels d'outils identiques.
- Debouncer l'`additionalContext` si on passe de stderr à une injection.

Source : audit ECC vs claude-crew du 2026-10-01

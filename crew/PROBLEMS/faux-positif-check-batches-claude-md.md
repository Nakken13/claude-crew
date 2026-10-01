# Faux positif `check_batches()` : `CLAUDE.md` pris pour une tâche inexistante

Statut : 🟡 en cours — tâche : `crew/TODO/faux-positif-check-batches-claude-md.md` (Batch A, cf. `crew/CLAUDE_BATCH.md`)

## Constat

`check_batches()` dans `scripts/crew_hook.py` (et sa copie `crew/crew_hook.py`)
extrait les slugs de tâches par la regex `` `([\w\-.]+\.md)` `` appliquée à
**tout** `crew/CLAUDE_BATCH.md`, pas seulement aux lignes de liste. Or l'en-tête
du template `template/crew/CLAUDE_BATCH.md` contient la prose « Voir § Batching
dans `CLAUDE.md` racine ». Résultat : chaque projet bootstrapé reçoit au Stop
l'avertissement « [batch] CLAUDE_BATCH.md référence une tâche inexistante :
`CLAUDE.md` ». Reproduit sur ce repo même.

## Impact

- Bruit stderr récurrent : throttlé, mais réémis à chaque expiration du
  cooldown, dans tous les projets dérivés du template.
- Tokens gaspillés à chaque Stop pour un faux signal.
- Dilue la crédibilité des vrais avertissements `[batch]` (référence à une
  tâche réellement disparue).

## Pistes

- Ne parser que les lignes de liste de tâches (`TASK_LINE_RE` existe déjà dans
  le hook) au lieu de tout le fichier.
- Ou exclure les noms en majuscules / documents connus (`CLAUDE.md`,
  `AGENTS.md`, `HISTORIQUE.md`...).
- Ou reformuler l'en-tête du template pour ne pas citer un `.md` en backticks
  (contournement seulement, ne corrige pas le parseur).

Source : audit ECC vs claude-crew du 2026-10-01

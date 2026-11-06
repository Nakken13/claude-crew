---
name: crew-status
description: Rapport lecture seule de l'état crew — batchs actifs et zones, tâches en cours, tests IA non cochés, TODO non classées. Trigger — "/crew-status", "où en est le projet", "état des batchs".
---

Lecture seule — ne modifie aucun fichier. Le calcul est fait par un script
déterministe ; ce skill présente son résultat. Complète le hook `Stop`
(sortie discrète en stderr) par une vue à la demande.

1. Lancer (plugin : `scripts/crew_hook.py` du plugin ; clone manuel :
   `crew/crew_hook.py`) :

   ```bash
ROOT="$(git rev-parse --show-toplevel)"; HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" status
```

2. Rapporter, depuis le JSON :
   - `active_batches` + `zone` ; tout `zone_overlaps` = **invariant violé**,
     à signaler explicitement (batchs + chemins), pas juste à lister ;
   - `current` : ratio `done/total` par tâche ;
   - `paused` : tâches en attente de validation visuelle/dev — à signaler
     nommément, pas comptées comme du travail en cours normal ;
   - `tests_ia_unchecked` : fichiers avec cases non cochées (ce qui reste à
     valider) ;
   - `todo_orphans` : en `TODO/` mais absentes de `CLAUDE_BATCH.md` (ni
     batch, ni « À classer ») → proposer `/crew-new-task` / `manager` ;
   - `bootstrap_pending` vrai : lancer `python check_placeholders.py` et
     inclure son résultat (placeholders `<...>` = scaffold non initialisé →
     `/crew-init`) ;
   - **Garde-fou checklists jamais cochées** (suggestion seule) : lire la
     ligne `Niveau :` de `crew/CLAUDE_CONTEXT/TESTS_POLICY.md` (`grep`, sans
     lire le fichier). Uniquement si le niveau est `full`, ou si le fichier
     est absent ou illisible (comportement historique `full`) : si les
     `- [ ]` de `crew/TESTS/{IA,DEV}` (hors `TESTS_DONE`) dominent
     nettement les `- [x]` (totaux via `grep -rhF … | wc -l`), proposer
     « N cases jamais cochées : passer en `light` dans `TESTS_POLICY.md` ? ».
     Jamais en `light`/`none`, jamais de modification du fichier.
   - `orphan_worktrees` : worktree `*-batch-*` sur disque sans session qui le
     porte (crash, ou `/crew-close-task` jamais lancé) — le signaler pour
     nettoyage manuel (`git worktree remove` / `git branch -d` par
     l'utilisateur), **jamais** le supprimer soi-même (travail non commité
     possible).

## Ce que ce skill ne fait pas

- N'écrit, ne déplace, ne coche rien — pur reporting.
- Ne remplace pas `/crew-new-task` / `/crew-close-task` pour agir.

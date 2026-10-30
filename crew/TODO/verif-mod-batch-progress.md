# Vérifier en réel le mod batch-progress

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-crew-radar.md` (séquence du batch).

**Description** : Barres `Task : [████░░] 4/6` et `Batch : [██████░░] 3/4` ; écoute `session.start` et `tool.call` ; lit la tâche active dans `crew/CURRENT_TASKS/`, `crew/CLAUDE_BATCH.md`, `crew_lock.json`.

Surface : bandeau `progress`. Événements : session.start, tool.call.
Fichiers : `hooks/mods/batch-progress.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Avec une tâche en CURRENT_TASKS, cocher une case `- [x]` via Edit et constater la mise à jour de la barre Task au `tool.call` suivant.
- [ ] Barrer une tâche (`~~slug.md~~`) dans CLAUDE_BATCH.md : la barre Batch progresse.
- [ ] Vérifier le choix de la tâche quand plusieurs sont en CURRENT_TASKS (association session via `crew_lock.json`).
- [ ] Cas limite : aucune tâche active, 0 case (division par zéro), `[s]` comptés comme skip, `CLAUDE_BATCH.md` ou `crew/` absent : bandeau masqué sans erreur.
- [ ] Vérifier qu'une exception interne n'interrompt jamais l'outil (catch « never disrupt »).
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Les ratios affichés correspondent exactement au décompte des cases et des tâches barrées. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

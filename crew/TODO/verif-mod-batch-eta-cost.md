# Vérifier en réel le mod batch-eta-cost

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-batch-progress.md` (séquence du batch).

**Description** : Estimation `Fin estimée : ~N min (~Xk tokens restants)` ; écoute `session.start`, `turn.complete` ; persiste `.claude/crew-batch-metrics.json` ; détecte les tâches clôturées via CLAUDE_BATCH.md/TODO/CURRENT_TASKS.

Surface : bandeau d'estimation. Événements : session.start, turn.complete.
Fichiers : `hooks/mods/batch-eta-cost.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Faire plusieurs tours sur une tâche en cours et constater une estimation plausible (bootstrap via progression des cases quand 0 tâche terminée).
- [ ] Clôturer une tâche (barrer + retirer de CURRENT_TASKS) : ses métriques sont écrites dans `.claude/crew-batch-metrics.json` (inspecter le JSON).
- [ ] Relancer la session : les métriques sont rechargées depuis le disque et l'estimation s'appuie dessus.
- [ ] Cas limite : fichier métriques absent, JSON corrompu, écriture impossible : fusion avec l'état mémoire, pas de crash.
- [ ] Cas limite : aucune tâche terminée ni case cochée, `crew/` absent : pas d'estimation, pas de NaN/Infinity.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Estimation cohérente et métriques persistées/relues correctement après clôture et redémarrage. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

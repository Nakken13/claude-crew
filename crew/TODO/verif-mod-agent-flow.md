# Vérifier en réel le mod agent-flow

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-file-lock-monitor.md` (séquence du batch).

**Description** : Arbre d'exécution des subagents (`Agent`, `Task`, personas) ; écoute `session.start`, `tool.call` ; commande `/crew-agents` ; volet `crew-agents`.

Surface : volet `crew-agents`. Événements : session.start, tool.call, command.run.
Fichiers : `hooks/mods/agent-flow.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Lancer `/crew-agents` : le volet s'ouvre ; relancer : il se ferme (toggle).
- [ ] Dispatcher une persona (ex. `ceo`) puis un `Agent` : le nœud apparaît avec statut, durée, outils appelés.
- [ ] Vérifier l'imbrication : outil appelé par un subagent actif rattaché à son nœud.
- [ ] Vérifier le passage en terminé/erreur à la fin du subagent.
- [ ] Cas limite : aucun subagent : état vide propre ; event sans `input`/`args`/nom : ignoré sans crash.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Arbre fidèle aux subagents réellement lancés, toggle fonctionnel. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

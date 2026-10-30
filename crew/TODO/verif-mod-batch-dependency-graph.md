# Vérifier en réel le mod batch-dependency-graph

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-stack-viewer.md` (séquence du batch).

**Description** : Kanban `/crew-board` (Todo | In Progress | Done | Blocked) et dépendances de zones entre batchs ; écoute `session.start`, `turn.complete`, commande `/crew-board` ; lit `crew/TODO`, `CURRENT_TASKS`, `CLAUDE_BATCH.md`, `crew_lock.json`.

Surface : volet `crew-board`. Événements : session.start, turn.complete, command.run.
Fichiers : `hooks/mods/batch-dependency-graph.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Ouvrir `/crew-board` : les tâches sont dans les bonnes colonnes (TODO, CURRENT_TASKS, barrées = Done).
- [ ] Créer deux batchs aux `Zone :` chevauchantes dont un actif : les tâches TODO de l'autre apparaissent en Blocked avec la raison.
- [ ] Vérifier le lien tâche vers session active (`crew_lock.json`) et le rafraîchissement à `turn.complete` et à l'invocation de la commande.
- [ ] Vérifier le toggle ouvrir/fermer.
- [ ] Cas limite : `CLAUDE_BATCH.md` vide/absent, tâche sans batch (« À classer »), `crew/` absent, worktree (lecture via mainRoot) : pas de crash.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Colonnes et blocages conformes à l'état réel de crew/ ; aucune exception. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

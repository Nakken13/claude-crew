# Vérifier en réel le mod crew-radar

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-prompt-cache-control.md` (séquence du batch).

**Description** : Bandeau `X Sessions | Y Current Tasks | Z Todo` ; écoute `session.start`/`turn.complete` (heartbeat)/`session.end` ; lock `.claude/crew-sessions.lock`, lit `crew/CURRENT_TASKS/`, `crew/TODO/`, `crew_lock.json` ; projectRoot via `session.start` (cwd). Modifs non committées en cours.

Surface : bandeau `radar`. Événements : session.start, turn.complete, session.end.
Fichiers : `hooks/mods/crew-radar.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Démarrer une session : le lock `.claude/crew-sessions.lock` est créé et le compteur affiche 1 session.
- [ ] Ouvrir une 2e session (même repo, puis worktree) : le compteur passe à 2 ; fermer l'une : retour à 1 après `session.end`.
- [ ] Déplacer une tâche TODO vers CURRENT_TASKS et constater la mise à jour des compteurs Current/Todo au tour suivant.
- [ ] Vérifier que le projectRoot retombe bien sur le cwd de `session.start` (commit 15d577f), y compris depuis un sous-dossier ou un worktree.
- [ ] Cas limite : `crew/` absent, dossiers vides : compteurs 0, pas d'exception ; lock corrompu/expiré (TTL 30 min) : purge propre.
- [ ] Cas limite : lock illisible ou non inscriptible : dégradation silencieuse.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Les trois compteurs reflètent l'état réel du disque et des sessions ouvertes, lock nettoyé à la sortie. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

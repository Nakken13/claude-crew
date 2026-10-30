# Vérifier en réel le mod stack-viewer

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-turn-inspector.md` (séquence du batch).

**Description** : Arbre de la stack chargée (CLAUDE.md, AGENTS.md, règles, MCP, skills, agents, mods) avec source/priorité ; écoute `session.start`, commande `/crew-stack` ; lit `.claude/settings.local.json`, `CLAUDE.md`, `AGENTS.md`, `crew/CLAUDE_CONTEXT/AGENTS.md`.

Surface : volet `crew-stack`. Événements : session.start, command.run.
Fichiers : `hooks/mods/stack-viewer.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Lancer `/crew-stack` : le volet liste les fichiers présents avec bonne source et priorité (P1/P2).
- [ ] Ajouter puis retirer un fichier (ex. `AGENTS.md`) et relancer : l'arbre suit.
- [ ] Vérifier la liste des mods (les 10 attendus) et des skills/agents/MCP.
- [ ] Cas limite : `.claude/` ou `crew/` absent, fichier illisible, `CLAUDE_PROJECT_DIR` non défini (`$.env.get` asynchrone) : entrées marquées absentes sans crash.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Arbre fidèle à l'état disque et à la session, toggle fonctionnel. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

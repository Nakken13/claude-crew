# Vérifier en réel le mod turn-inspector

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-agent-flow.md` (séquence du batch).

**Description** : Historique des tours (tokens in/out, cache read/write, outils, durée) ; écoute `tool.call`, `turn.complete`, `session.start` ; commande `/crew-turns` ; volet `crew-turns`.

Surface : volet `crew-turns`. Événements : session.start, tool.call, turn.complete, command.run.
Fichiers : `hooks/mods/turn-inspector.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Ouvrir `/crew-turns` après 3 tours avec outils variés : une ligne par tour avec tokens, cache, outils, durée corrects (comparer à `session.usage()`).
- [ ] Vérifier le toggle ouvrir/fermer et la persistance de l'historique pendant la session.
- [ ] Cas limite : tour sans usage, tour sans outil, tour très long (barre de progression bornée) : pas de NaN ni débordement.
- [ ] Vérifier qu'une erreur dans le handler `tool.call` ne bloque jamais l'outil.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Chaque tour correspond à une ligne exacte ; aucune erreur dans les logs. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

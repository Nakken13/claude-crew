# Vérifier en réel le mod prompt-cache-control

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-token-weather.md` (séquence du batch).

**Description** : Compte à rebours du prompt cache (TTL 5 min / 1 h) ; écoute `session.start` (timer 1 s, `$.env.get('CLAUDE_CACHE_TTL')` asynchrone), `turn.complete` (usage cache), `session.end` ; toast < 60 s ; volet `crew-cache`. Modifs non committées en cours.

Surface : volet `crew-cache` + toast. Événements : session.start, turn.complete, session.end.
Fichiers : `hooks/mods/prompt-cache-control.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [x] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod. _(14/14 verts, bloc cache OK)_
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs. _(session réelle impossible depuis ici → TESTS/DEV)_
- [x] Vérifier que `$.env.get('CLAUDE_CACHE_TTL')` (asynchrone, corrigé récemment) est bien résolu : lancer avec `CLAUDE_CACHE_TTL=1h` puis sans, constater TTL 3600 vs 300. _(unitaire : test TTL 1h/défaut ; constat en session réelle → TESTS/DEV)_
- [ ] Après un tour avec cache read/write, constater que le compte à rebours démarre et décrémente chaque seconde. _(session réelle → TESTS/DEV)_
- [x] Attendre/simuler < 60 s restantes : un seul toast d'alerte par rafraîchissement (pas de répétition). _(test timers réels : 1 seul toast, muet après session.end)_
- [ ] Ouvrir le volet `crew-cache` : totaux cache read/creation de session cohérents avec `crewRuntimeState`. _(session réelle → TESTS/DEV)_
- [x] `session.end` : le timer est arrêté (pas de fuite d'intervalle, pas de rendu après fin). _(mutation vérifiée : sans stop, le test échoue)_
- [x] Cas limite : aucun tour effectué (`lastRefreshAtMs` null) : pas de compte à rebours ni toast ; usage sans champs cache : pas de crash. _(test dédié)_
- [x] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche). _(aucune anomalie trouvée)_
- [x] Relancer `claude plugin test .` après toute correction liée et confirmer le vert. _(aucune correction ; suite 14/14)_

## Critère de réussite

Compte à rebours, toast unique et totaux corrects ; TTL env pris en compte ; timer stoppé à la fin. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

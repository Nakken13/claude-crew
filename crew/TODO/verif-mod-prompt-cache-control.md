# Vérifier en réel le mod prompt-cache-control

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-token-weather.md` (séquence du batch).

**Description** : Compte à rebours du prompt cache (TTL 5 min / 1 h) ; écoute `session.start` (timer 1 s, `$.env.get('CLAUDE_CACHE_TTL')` asynchrone), `turn.complete` (usage cache), `session.end` ; toast < 60 s ; volet `crew-cache`. Modifs non committées en cours.

Surface : volet `crew-cache` + toast. Événements : session.start, turn.complete, session.end.
Fichiers : `hooks/mods/prompt-cache-control.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Vérifier que `$.env.get('CLAUDE_CACHE_TTL')` (asynchrone, corrigé récemment) est bien résolu : lancer avec `CLAUDE_CACHE_TTL=1h` puis sans, constater TTL 3600 vs 300.
- [ ] Après un tour avec cache read/write, constater que le compte à rebours démarre et décrémente chaque seconde.
- [ ] Attendre/simuler < 60 s restantes : un seul toast d'alerte par rafraîchissement (pas de répétition).
- [ ] Ouvrir le volet `crew-cache` : totaux cache read/creation de session cohérents avec `crewRuntimeState`.
- [ ] `session.end` : le timer est arrêté (pas de fuite d'intervalle, pas de rendu après fin).
- [ ] Cas limite : aucun tour effectué (`lastRefreshAtMs` null) : pas de compte à rebours ni toast ; usage sans champs cache : pas de crash.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Compte à rebours, toast unique et totaux corrects ; TTL env pris en compte ; timer stoppé à la fin. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

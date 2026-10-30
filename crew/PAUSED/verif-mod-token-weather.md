# Vérifier en réel le mod token-weather

**Batch** : Vérification réelle des mods hooks. Premier du batch (valide aussi le socle `shared.ts`).

**Description** : Jauge météo 1 ligne (Clear/Cloudy/Storm/Compact soon) selon le ratio de contexte ; écoute `turn.complete`, lit `$.session.usage()` (correctifs récents).

Surface : bandeau `weather`. Événements : turn.complete.
Fichiers : `hooks/mods/token-weather.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [x] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod. — 11/11 verts (9 existants + 2 ajoutés : seuils, état conservé).
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Faire 2-3 tours et constater que la jauge affiche le bon palier (<50% Clear, 50-74% Cloudy, 75-89% Storm, >=90% Compact soon) en comparant au ratio réel de `session.usage()`.
- [ ] Vérifier le franchissement de seuils (49/50/74/75/89/90%) : consigner l'emoji et le libellé obtenus. — paliers/libellés/emoji aux 49/50/74/75/89/90 % vérifiés en test unitaire ; constat en session réelle → `TESTS/DEV`.
- [x] Cas limite : `session.usage()` indisponible/erreur ou fenêtre de contexte à 0 : pas de crash, pas de NaN%, bandeau neutre ou masqué. — couvert par test (`window` 0 → 200k, `usage()` qui lève → pas de NaN%).
- [x] Cas limite : événement `turn.complete` sans usage : l'ancien état est conservé. — couvert par test (état conservé à 60 %).
- [x] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche). — NaN direct consigné : `crew/PROBLEMS/token-weather-nan-entree-invalide.md`.
- [x] Relancer `claude plugin test .` après toute correction liée et confirmer le vert. — 11/11 verts.

## Critère de réussite

Le palier affiché correspond au ratio réel à chaque tour, sans exception dans les logs. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

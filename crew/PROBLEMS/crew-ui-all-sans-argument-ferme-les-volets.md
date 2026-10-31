# `/crew-ui all` sans `on`/`off` bascule au lieu d'ouvrir

Statut : ✅ corrigé (`focus` omis sauf `true`, test ajouté) ; reste : l'erreur du `.catch` d'ouverture auto est encore avalée (trouvé en vérifiant `verif-mod-prompt-cache-control`)

## Constat

En session réelle, `/crew-ui` affiche les volets OFF. `/crew-ui all` répond ensuite
« ⚪ Volets Zero-Token crew-mates fermés. » alors que l'utilisateur voulait les ouvrir.

## Cause (confirmée par la doc des types et l'erreur d'un collègue)

`PaneOpenArgs.focus` est typé `focus?: true` : `focus: false` est refusé par l'hôte
(`ui.open: focus is true or left out (host check)`). Deux appels le passent :

- `/crew-ui all` (`hooks/register.ts` ~l.648) : `focus: paneId === 'crew-board'` vaut `false` pour 4 volets sur 5 -> erreur locale.
- ouverture au démarrage (`601192d`, ~l.257) : `focus: false`, avalé par `.catch(() => undefined)` -> aucun volet ne s'ouvre, sans trace.

Piste de correctif : n'envoyer `focus` que s'il vaut `true` (omettre le champ sinon), et logger l'erreur du `.catch`.

## Contournement

`/crew-ui all on` (explicite).

## Pistes (pas de correctif dans la tâche de vérification)

- `all` sans argument = toujours ouvrir, ou documenter la bascule dans l'usage affiché.
- Resynchroniser `crewUiState.panes` quand un volet se ferme.

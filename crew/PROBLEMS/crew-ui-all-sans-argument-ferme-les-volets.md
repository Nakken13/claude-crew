# `/crew-ui all` sans `on`/`off` bascule au lieu d'ouvrir

Statut : 🔴 à traiter (trouvé en vérifiant `verif-mod-prompt-cache-control`)

## Constat

En session réelle, `/crew-ui` affiche les volets OFF. `/crew-ui all` répond ensuite
« ⚪ Volets Zero-Token crew-mates fermés. » alors que l'utilisateur voulait les ouvrir.

## Cause probable (lecture de `hooks/register.ts`, ~l.629-665, non reproduite)

Sans argument, `all` bascule : `shouldEnable = !allPanesCurrentlyOpen`, calculé sur
`crewUiState.panes`, un état interne. Il peut diverger de ce qui est affiché
(volet fermé à `Échap` via `closeOnEscape`, ou `601192d` qui met l'état à `true`
à `session.start`). Si l'état dit « tout ouvert », `all` ferme.

## Contournement

`/crew-ui all on` (explicite).

## Pistes (pas de correctif dans la tâche de vérification)

- `all` sans argument = toujours ouvrir, ou documenter la bascule dans l'usage affiché.
- Resynchroniser `crewUiState.panes` quand un volet se ferme.

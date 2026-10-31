# token-weather : bandeau tronqué + piège de la copie installée périmée

Statut : 🟡 partiel (le « 0 % » n'était pas un bug du code ; la troncature reste à traiter)

## Contexte

En vérifiant `verif-mod-token-weather`, la jauge restait à 0 %. Sonde temporaire
dans `hooks/register.ts` (retirée) : `$.session.usage()` répond
`context = {tokens: 87628, window: 1000000, percent: 9}` et la jauge affiche
`☀️ Clear [█░░░░░░░]`, donc correct.

## Cause du 0 %

Une copie installée de `crew-mates` (`~/.claude/plugins/cache/crew-mates/1.0.0/`)
était chargée à la place du worktree : sa `register.ts` n'appelle pas
`session.usage()` (0 occurrence). Désactivée (`claude plugin disable crew-mates`),
le worktree donne le bon chiffre. À mettre à jour (`claude plugin update`) après merge du batch.

## Reste ouvert (non traité dans la tâche de vérification)

1. Le texte du bandeau est tronqué en terminal étroit : `[█░░░░░░░] tokens restants)`,
   le pourcentage et le début de la parenthèse sont coupés.
2. Le `catch {}` de `register.ts` (~l.344) avale toute erreur de `session.usage()` sans trace.
   Un log d'erreur éviterait de retomber sur un 0 % muet.

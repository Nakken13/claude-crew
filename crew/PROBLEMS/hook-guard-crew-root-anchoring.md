# Garde-fou mécanique pour l'ancrage racine de crew/

Statut : 🔴 ouvert

## Contexte

`ancrer-crew-racine-repo` (clôturée 2026-09-03, cf. `HISTORIQUE.md`) a fixé
le bug du `crew/` fantôme en sous-dossier (mono-subtree) uniquement au
niveau prose : `manager.md` et les 6 skills `crew-*` disent maintenant
explicitement de résoudre la racine avant d'écrire sous `crew/`. Mais ça
reste une instruction LLM — un agent peut toujours l'oublier.

Suggestion (review `requesting-code-review` sur cette tâche) : le hook
`crew/crew_hook.py` gate déjà d'autres opérations via `PreToolUse`
(matcher `Bash|Edit|Write|MultiEdit`, cf. `gate_pretooluse`). Un garde-fou
mécanique similaire pourrait bloquer/avertir sur une écriture relative
`crew/...` quand `cwd != racine du repo`, plutôt que de dépendre uniquement
de la prose.

## Pourquoi pas fait maintenant

Zone d'impact de `ancrer-crew-racine-repo` limitée à la documentation
(`manager.md`, `SKILL.md`, `CLAUDE.md`) — modifier `crew/crew_hook.py`
est un changement de code séparé, plus risqué (le hook gate déjà plusieurs
choses, cf. historique des incidents de lock/collision), mérite sa propre
tâche avec sa propre revue plutôt que d'être ajouté en périphérie ici.

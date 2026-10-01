# Continuité de session : pas de hook SessionStart ni PreCompact

Statut : 🟡 en cours — tâche : `crew/TODO/continuite-session-sessionstart-precompact.md` (Batch A, cf. `crew/CLAUDE_BATCH.md`)

## Constat

Aucun hook `SessionStart` ni `PreCompact` dans le plugin. La reprise passe
par `crew-start`, qui relit `crew/` à la main (listing + lecture des fichiers
`CURRENT_TASKS/`, `CLAUDE_BATCH.md`, locks), et rien ne survit à une
compaction de contexte. `crew/CLAUDE_CONTEXT/HISTORIQUE.md` (752 lignes) n'est
jamais injecté, ce qui est correct en soi, mais aucun digest ne l'est non plus.

Comparaison ECC : `SessionStart` injecte un digest plafonné (8000 chars,
réglable par env, désactivable) ; `PreCompact` écrit un snapshot d'état.

Contrainte crew à respecter : `crew/` reste la source unique de vérité, pas
de store parallèle dans `~/.claude`.

## Impact

- Chaque reprise coûte plusieurs lectures de fichiers (tokens + latence)
  pour reconstruire un état que le hook pourrait fournir en une injection.
- Après compaction, l'agent perd l'état de la tâche en cours et des batchs
  actifs ; risque de collision ou de travail dupliqué.

## Pistes

- `SessionStart` injectant un digest plafonné (~2k chars) : contenu de
  `CURRENT_TASKS/` et `PAUSED/`, batchs actifs, locks d'autres sessions,
  3 derniers titres de `HISTORIQUE.md`. Désactivable par profil/env.
- `PreCompact` écrivant un snapshot pur fichier sous `crew/` (pas de store
  externe), relu par le digest SessionStart.
- Alléger `crew-start` en conséquence pour ne pas doubler les lectures.
- Attention au coût du spawn (cf. `latence-hook-pretooluse-spawn-python.md`) :
  un hook de plus = un spawn de plus, à chiffrer.

Source : audit ECC vs claude-crew du 2026-10-01

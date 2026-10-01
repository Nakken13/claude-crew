# Latence du hook PreToolUse : un spawn Python à chaque appel outil

Statut : 🟡 en cours — tâche : `crew/TODO/latence-hook-pretooluse-spawn-python.md` (Batch A, cf. `crew/CLAUDE_BATCH.md`)

## Constat

Le hook PreToolUse (matcher `Bash|Edit|Write|MultiEdit`) spawn
`python scripts/crew_hook.py` à **chaque** appel outil. Mesures sur Windows 11 :

- 540-1200 ms par appel, dont 500-1000 ms de pur démarrage Python
  (`python -I -S` seul ~800 ms).
- Node nu : 380-740 ms, donc changer de langage ne résout pas le problème.
- Hook Stop ~740 ms.

Aucun profil ni gating : `userConfig` est absent de
`.claude-plugin/plugin.json`, la garde anti-collision tourne même en session
solo où elle est sans objet. Comparaison ECC : profil `minimal/standard/strict`
via `userConfig.hook_profile` + variable d'env + liste d'ids de hooks
désactivables ; dispatchers consolidés ; split sync/async.

## Impact

- Latence perçue sur chaque Edit/Write/Bash, cumulée sur une session entière
  (plusieurs centaines d'appels = plusieurs minutes perdues).
- Coût payé même quand aucune autre session n'est active (cas majoritaire).
- Pas de levier utilisateur pour alléger sans désactiver le plugin entier.

## Pistes

- Gating par profil (`userConfig` dans `plugin.json` + env) sur le modèle ECC.
- Pré-test shell quasi gratuit avant le spawn Python : n'invoquer le script
  que si `crew/crew_lock.json` montre une autre session active.
- `"async": true` sur les hooks qui ne rendent aucune décision bloquante
  (ex. SessionEnd).
- Consolider les dispatchers pour limiter le nombre de spawns par événement.

Source : audit ECC vs claude-crew du 2026-10-01

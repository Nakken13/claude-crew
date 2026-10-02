# Latence PreToolUse : pré-filtre shell + marqueur `.gate_armed` avant le spawn Python

Zone d'impact : `hooks/hooks.json`, `scripts/crew_hook.py`, `crew/crew_hook.py`
(copie synchronisée), `crew/test_crew_hook.py`, `template/.gitignore` (+ `.gitignore`
racine), `scripts/dev/verify_plugin_package.py` (`check_hooks_json`), `README.md`
(documentation de l'escape hatch).
Source : `crew/PROBLEMS/latence-hook-pretooluse-spawn-python.md` — audit § 4.B.
Arbitrage `architect` : rendu (pré-filtre shell + marqueur fichier, pas de profil
`userConfig` complet).

## Description

Le hook PreToolUse spawn Python à chaque Edit/Write/Bash (540-1200 ms, dont
500-1000 ms de démarrage Python), y compris en session solo où la garde
anti-collision est sans objet. Éviter le spawn dans le cas majoritaire : `save_locks()`
maintient un marqueur `crew/CLAUDE_CONTEXT/.gate_armed` présent ssi ≥ 2 sessions
dans `crew_lock.json` ; la commande shell du hook teste le marqueur avant d'invoquer
Python. Les claims Bash (déplacement TODO → CURRENT_TASKS, `crew-resume:`) doivent
toujours atteindre le script (ils écrivent le verrou même en solo).

**Dépendance (Batch A, tâche 1 `verrou-partage-worktrees.md`)** : après ce fix, le verrou
vit dans `MAIN_ROOT/crew/CLAUDE_CONTEXT/` alors que le pré-filtre shell teste
`$CLAUDE_PROJECT_DIR/crew/CLAUDE_CONTEXT/.gate_armed` (= le worktree courant). Le
marqueur `.gate_armed` doit donc être posé/retiré par `save_locks()` dans le checkout
principal **ET** dans chaque worktree enregistré dans le lock (champ `worktree`),
sinon une session worktree saute la garde. Ajouter le test correspondant.

## Actions

- [ ] Mesure AVANT : chronométrer 10 appels du hook PreToolUse (payload Edit factice
      piped au script, et via la commande shell complète de `hooks.json`) ; noter la
      médiane en ms dans le fichier de tâche puis dans HISTORIQUE à la clôture.
- [ ] TDD rouge/vert `save_locks()` : test où le lock contient 1 session → pas de
      `crew/CLAUDE_CONTEXT/.gate_armed` ; 2 sessions → marqueur créé ; retour à 1
      (ou 0, purge SessionEnd) → marqueur supprimé. Écriture idempotente, tolérante
      aux erreurs (best-effort, jamais d'exception remontée).
- [ ] `hooks/hooks.json` : scinder l'entrée PreToolUse en deux. Entrée
      `Edit|Write|MultiEdit` : commande shell
      `[ -e "$CLAUDE_PROJECT_DIR/crew/CLAUDE_CONTEXT/.gate_armed" ] || exit 0`
      puis spawn Python inchangé. Entrée `Bash` : capturer stdin (`IN=$(cat)`),
      laisser passer vers Python si marqueur présent OU si `$IN` matche le motif de
      claim (`git mv` vers CURRENT_TASKS, `crew-resume:`) via `grep -qE`, sinon
      `exit 0` ; re-piper `$IN` au script. Garder les `statusMessage`/`timeout`.
- [ ] `"async": true` sur les entrées `SessionEnd` et `PostToolUse` (`Write`,
      `spec_to_task_hook.py`) — aucune décision bloquante rendue. Laisser `Stop`
      et `PreToolUse` synchrones.
- [ ] Escape hatch `CREW_HOOK_PROFILE=minimal` : en tête du `main()` de
      `crew_hook.py`, si la variable vaut `minimal`, les événements PreToolUse
      sortent immédiatement (exit 0) ; Stop/SessionEnd continuent (index, verrous).
      Test unitaire + une ligne dans `README.md`.
- [ ] Gitignore : ajouter `crew/CLAUDE_CONTEXT/.gate_armed` dans `template/.gitignore`
      (section « État interne des hooks crew ») et dans le `.gitignore` racine de ce repo.
- [ ] Adapter `scripts/dev/verify_plugin_package.py` (`check_hooks_json`) si la
      nouvelle forme de commande (pré-filtre avant `crew_hook.py`) ou le split en
      deux entrées PreToolUse le fait échouer ; `verify_plugin_package.py` vert.
- [ ] Synchroniser `crew/crew_hook.py` ↔ `scripts/crew_hook.py` ; pytest vert.
- [ ] Mesure APRÈS : refaire les 10 appels en session solo (pas de marqueur) et avec
      marqueur présent ; reporter les deux médianes ; vérifier qu'un déplacement
      TODO → CURRENT_TASKS lancé sans marqueur passe toujours par Python (verrou
      écrit dans `crew_lock.json`).

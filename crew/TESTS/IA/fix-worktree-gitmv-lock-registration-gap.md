# fix-worktree-gitmv-lock-registration-gap

Validation du fix : `git mv crew/TODO/<slug>.md crew/CURRENT_TASKS/<slug>.md`
lancé depuis un worktree de batch enregistre desormais le verrou live dans
`crew/CLAUDE_CONTEXT/crew_lock.json` (+ régénère `BATCH_LOCKS.md`) au moment
même du `PreToolUse`, sans attendre le `Stop` suivant — voir
`crew/CLAUDE_CONTEXT/HISTORIQUE.md` et `crew/crew_hook.py`
(`_claim_lock`/`_claim_git_mv_lock`/`gate_pretooluse`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py -v` → 13 passed, y compris
      les 5 nouveaux scénarios `test_gate_pretooluse_git_mv_*` (registration
      immédiate, régénération `BATCH_LOCKS.md` immédiate, blocage même-slug
      déjà verrouillé, blocage TOCTOU sur relecture fraîche, idempotence avec
      la boucle `started` du Stop en fallback).
- [ ] 🔍 Bout en bout réel (pas simulé en mémoire) : créer un vrai
      `git worktree add -b crew/batch-<slug> ../<repo>-batch-<slug> main`,
      catégoriser une tâche de test dans `crew/CLAUDE_BATCH.md`, puis depuis
      CE worktree : `echo '{"session_id":"sessX","hook_event_name":
      "PreToolUse","tool_name":"Bash","tool_input":{"command":"git mv
      crew/TODO/<slug>.md crew/CURRENT_TASKS/<slug>.md"}}' | python
      crew/crew_hook.py` → exit 0, et `crew/CLAUDE_CONTEXT/crew_lock.json`
      (checkout principal, partagé) contient déjà `sessX` avec ce slug
      **avant même d'exécuter le `git mv` réel** — pas besoin d'un tour Stop.
- [ ] 🔍 Même scénario avec une 2e session (`sessY`) qui tente le même slug
      (ou une voisine du même batch) pendant que `sessX` le tient encore →
      exit code 2, message stderr explicite, `crew_lock.json` inchangé côté
      `sessY`.
- [ ] 🔍 `python scripts/dev/verify_plugin_package.py` → PASS, `crew/
      crew_hook.py` et `scripts/crew_hook.py` restent synchronisés
      (`diff crew/crew_hook.py scripts/crew_hook.py` vide).
- [ ] 🔍 Nettoyer le worktree/branche de test créés pour ce scénario
      (`git worktree remove` + `git branch -d`) une fois la validation faite.

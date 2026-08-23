# worktree-batch-isolation

Validation de l'isolation physique par `git worktree` par batch actif
(Layer 1) + du gate `PreToolUse` durci sur `Bash|Edit|Write|MultiEdit`
(Layer 2) — voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md` et
`docs/superpowers/specs/2026-08-22-worktree-batch-isolation-design.md`.

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 Suite de smoke tests (fonctions pures : `_batch_slug`,
      `_worktree_paths_for`, `_slug_session_map`, `_register_task_lock`,
      `_locked_zones_by_others`, `_repo_relative_path`, `_path_matches_zone`,
      `_path_locked_by_other`, `_extract_candidate_paths`, `purge_stale_locks`
      sur le nouveau schéma `{"sessions": {...}}`) — tous les cas passent, y
      compris `_repo_relative_path` avec un chemin ABSOLU (racine du dépôt et
      racine d'un worktree de batch) et `_path_matches_zone` avec une zone à
      glob (`crew-*`).
- [ ] 🤖 `/crew-start` simulé sur 2 batches à zones **non chevauchantes**
      depuis 2 sessions (`session_id` distincts) : deux worktrees
      `../<repo>-batch-<slug-a>/` et `../<repo>-batch-<slug-b>/` créés (via
      `git worktree add -b crew/batch-<slug> ...`), chaque session n'écrit
      que dans le sien — zéro fichier partagé écrit hors de son propre
      worktree.
- [ ] 🤖 `/crew-close-task` avec un rebase propre (`crew/batch-<slug>` sur
      `main` courant) → merge fast-forward réussi, `git worktree remove` +
      `git branch -d` exécutés, entrée session correspondante disparue de
      `crew/CLAUDE_CONTEXT/crew_lock.json` après le `Stop`/`SessionEnd`
      suivant.
- [ ] 🤖 `/crew-close-task` avec un changement conflictuel sur `main` : le
      rebase échoue → `git rebase --abort`, worktree + branche survivent
      intacts, fichiers en conflit listés, mais l'entrée session est quand
      même vidée de `crew_lock.json` au `Stop`/`SessionEnd` suivant.
- [ ] 🔍 Gate durci `Edit`/`Write`/`MultiEdit` — **`file_path` ABSOLU**
      (c'est le seul format que ces tools envoient réellement ; un test avec
      un chemin déjà relatif masquerait une régression sur `_repo_relative_
      path`) : `echo '{"session_id":"sess-B","hook_event_name":"PreToolUse",
      "tool_name":"Edit","tool_input":{"file_path":"<chemin ABSOLU sous une
      Zone: verrouillee par sess-A, ex. crew/crew_hook.py resolu>"}}' |
      python crew/crew_hook.py` → exit code 2, stderr contient
      `[worktree-gate]`. Même chemin absolu sans verrou actif, ou verrouillé
      par `sess-B` elle-même → exit code 0, pas de sortie. Refaire le même
      test avec un chemin absolu sous une `Zone:` à glob (`.claude/skills/
      crew-*`, cf. `crew/CLAUDE_BATCH.md`) → également bloqué (vérifie
      `_path_matches_zone`/`fnmatch`, pas seulement le préfixe simple).
- [ ] 🔍 Gate durci `Bash` générique : commande `rm`/`mv`/`cp`/redirection
      `>` ciblant un chemin sous une `Zone:` verrouillée par une autre
      session → exit code 2 ; commande sans rapport avec une zone verrouillée
      → exit code 0.
- [ ] 🔍 Purge TTL : une entrée `sessions.<sid>` de `crew_lock.json` datée de
      plus de 6h est retirée en bloc (tasks + worktree + branch) au `Stop`
      suivant ; `/crew-status` (étape worktrees orphelins) signale alors le
      worktree correspondant comme orphelin s'il est toujours sur disque.
- [ ] 🔍 Collision de reprise : une 2e session tentant `/crew-start`
      (marqueur `crew-resume:<slug>`) sur un batch dont le worktree/verrou
      est déjà tenu par un autre `session_id` est bloquée (exit 2) avant
      toute édition.
- [ ] 🔍 `crew/CLAUDE_CONTEXT/crew_lock.json` reste un JSON valide et de
      forme `{"sessions": {...}}` après une séquence Stop/PreToolUse/
      SessionEnd mêlée (pas de régression vers l'ancien format plat).
- [x] 🔍 `python scripts/dev/verify_plugin_package.py` → PASS, `crew/
      crew_hook.py` et `scripts/crew_hook.py` restent synchronisés.

## 🖱️ Voir aussi crew/TESTS/DEV/worktree-batch-isolation.md

Le scénario multi-session réel (deux vraies sessions Claude Code, deux
terminaux) n'est pas scriptable depuis une seule session IA — checklist
séparée côté DEV.

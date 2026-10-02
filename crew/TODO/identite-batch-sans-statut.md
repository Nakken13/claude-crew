# Identité de batch indépendante du statut affiché dans le header

Zone d'impact : `crew/crew_hook.py` + `scripts/crew_hook.py` (copies synchronisées),
`crew/test_crew_hook.py`, `skills/crew-start/SKILL.md` + miroir
`.claude/skills/crew-start/SKILL.md` (algorithme de slug worktree décrit étapes
2A-ter / 5B-bis). Dashboard à vérifier (affiche `batch` du lock).
Source : désynchro constatée sur voyageo.

## Description

L'identité d'un batch est aujourd'hui le header `## …` **complet, statut inclus**.
Ex. voyageo : lock `"Batch — Yuna déterminisme … · 🔄 en cours (prochaine : 04)"`
alors que le header est devenu `(prochaine : 05)` → `_register_task_lock`
(branche `info.get("batch") != section["header"]`, ~l.465) signale une incohérence
de batch alors que c'est le même. Le slug worktree/branche (`_batch_slug` /
`_worktree_paths_for`) embarque aussi le statut (`…-pas-d-marr`,
`…-en-cours-prochaine-04`) : quand le statut change, le `worktree` enregistré
(`../voyageo-batch-yuna-…-prochaine-04`) ne correspond plus à rien.

Fix : clé de batch normalisée = header tronqué au premier ` · ` puis trim, utilisée
pour la valeur `batch` du lock, les comparaisons et le slug worktree/branche.
Compat : un ancien verrou à clé longue reste reconnu (normaliser des deux côtés
avant comparaison).

Attention migration : un worktree déjà créé avec un slug contenant le statut ne
sera plus retrouvé par le nouveau slug — documenter dans `crew-start` (réutiliser
via `git worktree list` si un worktree `…-batch-<slug-normalisé>*` existe, ou le
signaler) plutôt que d'en créer un doublon silencieusement.

## Actions

- [ ] `grep` des consommateurs de `section["header"]` / `info["batch"]` /
      `_batch_slug` dans `crew/crew_hook.py`, `scripts/dashboard/`, skills
      `crew-*` ; lister les points à modifier dans ce fichier.
- [ ] TDD rouge : `test_batch_key_strips_status_suffix` (header avec ` · 🔄 en cours
      (prochaine : 04)` → clé sans statut) ;
      `test_header_status_change_no_incoherence` (lock créé avec statut 04, header
      passé à 05 → aucun warning `[crew_lock] incoherence` sur stderr) ;
      `test_worktree_slug_stable_across_status_change` ;
      `test_legacy_long_batch_key_matches_normalized`.
- [ ] Implémenter `_batch_key(header)` (tronque au premier ` · `, trim) ;
      `_batch_slug`/`_worktree_paths_for` partent de `_batch_key` ;
      `_register_task_lock` stocke et compare des clés normalisées (les deux côtés).
- [ ] Passer en revue les autres comparaisons de header (`check_zone_overlaps`,
      `find_section_for`, `regen_batch_locks_md`, gate PreToolUse) pour qu'elles
      utilisent la clé normalisée ; tests existants verts.
- [ ] Mettre à jour l'algorithme de slug décrit dans `skills/crew-start/SKILL.md`
      (étape 2A-ter) + miroir `.claude/skills/crew-start/SKILL.md` : tronquer au
      premier ` · ` avant de slugifier ; ajouter la consigne de réutilisation d'un
      worktree existant à ancien slug.
- [ ] Synchroniser `crew/crew_hook.py` ↔ `scripts/crew_hook.py` ;
      `pytest crew/test_crew_hook.py` + `scripts/dashboard/test_server.py` verts.

# Verrou anti-collision partagé entre checkout principal et worktrees de batch

Zone d'impact : `crew/crew_hook.py` + `scripts/crew_hook.py` (copies synchronisées
à la main), `crew/test_crew_hook.py`. Dashboard (`scripts/dashboard/*`) : aucun
changement attendu (passe par `h.LOCKS_FILE`) — à confirmer par ses tests.
Source : faux positifs/désynchro constatés sur les projets cibles voyageo et
time2cook (suite du fix `fix-zone-overlap-faux-positifs`, commit 13741dd).
Arbitrage `architect` : option B (verrou centralisé dans le checkout principal,
résolution sans spawn git).

## Description

`ROOT` = `CLAUDE_PROJECT_DIR` (ou parent du script), donc chaque worktree de batch
a son propre `crew/CLAUDE_CONTEXT/crew_lock.json` : une session dans le checkout
principal et une session dans `../<repo>-batch-<slug>/` ne voient pas leurs verrous
mutuels (preuve : `voyageo-batch-perf-…/crew/CLAUDE_CONTEXT/crew_lock.json`
distinct de celui du principal). La garde anti-collision est donc aveugle entre
worktrees — exactement le cas qu'elle doit couvrir.

Fix : le verrou (`crew_lock.json`) et son mutex vivent dans
`MAIN_ROOT/crew/CLAUDE_CONTEXT/`, `MAIN_ROOT` étant le checkout principal résolu
**sans spawn git** :
- `ROOT/.git` est un dossier → `MAIN_ROOT = ROOT` ;
- `ROOT/.git` est un fichier → lire la ligne `gitdir:` (chemin absolu ou relatif à
  ROOT, normaliser `/` et `\`), lire `commondir` dans ce dossier (relatif au gitdir),
  `MAIN_ROOT` = parent du common dir ;
- fallback silencieux `MAIN_ROOT = ROOT` si lecture impossible, repo bare, ou pas de
  `crew/` dans le checkout principal résolu.

Reste **local au checkout** (ne pas migrer) : `DIRS`, `SNAP` (`.task_state.json`,
critique : le diff d'état est par checkout), `BATCH_FILE`, `HISTORIQUE`, `INDEX`,
`auto_commit_closure`.

Risque connu, **hors scope** (à décider séparément, ouvrir un PROBLEMS si besoin) :
le `CLAUDE_BATCH.md` d'un worktree peut être en retard sur celui du principal
(sections lues localement) → zones/headers comparés à partir de sources différentes.

## Actions

- [ ] TDD rouge — résolution `MAIN_ROOT` (fixtures `tmp_path`, faux `.git`) :
      `test_main_root_from_worktree_git_file`,
      `test_main_root_relative_gitdir_and_backslashes`,
      `test_main_root_fallback_no_git`, `test_main_root_fallback_bare_repo`,
      `test_main_root_fallback_main_without_crew`.
- [ ] Implémenter `_resolve_main_root(root)` (pur, sans subprocess, aucune exception
      remontée) ; constantes `MAIN_ROOT`, `LOCK_CTX = MAIN_ROOT / "crew" /
      "CLAUDE_CONTEXT"`, `LOCKS_FILE`/`LOCKS_MUTEX` sous `LOCK_CTX`. Tests verts.
- [ ] TDD rouge/vert — verrou partagé : `test_worktree_session_writes_main_lock`,
      `test_gate_main_blocks_zone_claimed_from_worktree` et son inverse
      (`test_gate_worktree_blocks_zone_claimed_from_main`).
- [ ] `_worktree_paths_for` : utiliser `MAIN_ROOT.name` (pas `ROOT.name`, sinon
      chemin `../<repo>-batch-x-batch-y` depuis un worktree) —
      `test_worktree_paths_use_main_root_name`.
- [ ] `_repo_relative_path` et `purge_closed_task_locks` : résoudre les chemins de
      worktree depuis `MAIN_ROOT` (garder la garde `.git is_dir()` existante) ;
      tests existants de purge worktree (commit d280db8) toujours verts.
- [ ] `_throttle_warnings` : scoper `warned` par checkout (clé incluant ROOT) pour
      que deux checkouts partageant le lock ne se masquent pas leurs warnings —
      `test_throttle_warned_scoped_per_checkout`.
- [ ] `regen_batch_locks_md` : n'écrire `BATCH_LOCKS.md` que si `ROOT == MAIN_ROOT` —
      `test_batch_locks_md_not_written_from_worktree`.
- [ ] Migration legacy : au premier passage depuis un worktree, si un
      `ROOT/crew/CLAUDE_CONTEXT/crew_lock.json` local existe, le fusionner dans le
      lock partagé **sous mutex** (par session, `since` le plus récent gagne), puis le
      supprimer — `test_legacy_worktree_lock_merged_then_removed`.
- [ ] Non-régression : `test_task_state_snapshot_stays_local` (`SNAP` reste sous ROOT).
- [ ] Synchroniser `crew/crew_hook.py` ↔ `scripts/crew_hook.py` (seule la ligne
      `ROOT = …` doit différer) ; `pytest crew/test_crew_hook.py` et
      `pytest scripts/dashboard/test_server.py` verts.
- [ ] Note de dépendance vérifiée : la TODO `latence-hook-pretooluse-spawn-python.md`
      mentionne que `.gate_armed` doit être posé dans le principal ET chaque
      worktree enregistré (déjà ajouté au découpage, relire avant clôture).

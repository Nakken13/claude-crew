# Tests — verrou partagé entre checkout principal et worktrees

Chantier : `verrou-partage-worktrees` (hook `crew/crew_hook.py` + miroir `scripts/crew_hook.py`).

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py scripts/dashboard/test_server.py -q` → tout vert.
- [ ] 🔍 `diff <(sed 's/^ROOT = .*//' crew/crew_hook.py) <(sed 's/^ROOT = .*//' scripts/crew_hook.py)` → aucune différence.
- [ ] 🔍 Dans un vrai worktree de batch, `python -c "import sys; sys.path.insert(0,'crew'); import crew_hook as h; print(h.MAIN_ROOT, h.LOCKS_FILE)"` → `LOCKS_FILE` pointe sous le checkout principal.
- [ ] 🔍 Lock legacy : poser un `crew_lock.json` local dans un worktree, lancer un Stop depuis ce worktree → fusionné dans le lock du principal puis supprimé.
- [ ] 🔍 Repli : worktree dont le principal n'a pas `crew/CLAUDE_CONTEXT/` → pas de crash du hook Stop.

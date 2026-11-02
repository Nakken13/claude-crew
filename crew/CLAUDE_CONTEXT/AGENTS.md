# Guide global — invariants produit + anti-patterns

Guide de contexte étendu, lu uniquement quand une règle cross-stack est
ambiguë (sinon lire l'`AGENTS.md` du subtree concerné suffit). À remplir au
fil du projet avec les invariants qui ne sont écrits nulle part ailleurs :
décisions produit qui ne se déduisent pas du code, pièges déjà rencontrés,
anti-patterns à ne pas réintroduire.

## Commit auto à la clôture d'une tâche crew

Clore une tâche crew (fichier disparu de `crew/CURRENT_TASKS/` + nouvelle
entrée dans `crew/CLAUDE_CONTEXT/HISTORIQUE.md` dans le même tour) déclenche
un commit git **local uniquement**, scopé à `crew/` (voir
`auto_commit_closure` dans `crew/crew_hook.py`, event Stop). Le `git push`
n'est **jamais** automatique — reste toujours une décision humaine
explicite. Incident source : un changement hors `crew/` avait été committé
et poussé sans revue lors d'une session qui n'avait jamais formellement clos
sa tâche ; ce commit auto donne une trace git systématique de chaque
clôture sans rien pousser à la place de l'utilisateur.

## Piège : copies synchronisées (repo source du plugin)
- Modifier `CLAUDE.md` racine → recopier à l'identique dans `template/CLAUDE.md` **et** `~/.claude/templates/project-scaffold/` ; vérifier avec `python scripts/dev/verify_plugin_package.py`.
- Moteur en double : `crew/crew_hook.py` ↔ `scripts/crew_hook.py` (seule la ligne `ROOT =` diffère), `crew/crew_update.py` ↔ `scripts/crew_update.py`, `.claude/{skills,agents}` ↔ `{skills,agents}/` : toute édition va dans les deux.
- Tests : `python -m pytest crew/` et `claude plugin test .` (`npx vitest` seul échoue : `claude-code/testing` introuvable).
- Données de suivi `crew/` (TODO, CURRENT_TASKS, PAUSED, PROBLEMS, ICEBOX, TESTS, CLAUDE_BATCH.md, HISTORIQUE.md) gitignorées : jamais dans un worktree, travailler dans le checkout principal.

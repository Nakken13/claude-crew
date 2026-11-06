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
## Claims distants (plusieurs devs sur le même repo)

Opt-in : `remote_claims : true` dans `crew/CLAUDE_CONTEXT/CREW_CONFIG.md` (défaut
`false` ; chaque dev l'active pour être protégé, `claims_remote` change le remote,
`origin` par défaut ; `claims_ref : refs/heads/crew-claims` = repli sur une branche si
le serveur refuse les refs custom). Les dossiers `crew/` restent la vérité de l'état des tâches ;
la ref git `refs/crew/claims` (poussée seule, jamais sur `main`) ajoute « qui fait
quoi » + les tâches `TODO` publiées : un `claims.json` slug → `{status, owner,
author, batch, zone, branch, ts, title, body}`.

Commandes (`python crew_hook.py claims …`, lancées par `/crew-start`,
`/crew-new-task`, `/crew-close-task`) : `fetch` · `claim <slug> --session --batch
--branch --zone` · `release <slug> [--done]` · `publish <slug> --title --zone
--body-file` · `check-dup --title --zone` · `materialize <slug>` · `list`.
`next-task` fusionne les claims distants (raison « claim distant : <owner> ») ;
le dashboard les affiche en Kanban (lecture seule) ; le digest de session liste
les tâches ouvertes (sans réseau).

**Garanti** (devs en ligne qui utilisent la synchro) : claim atomique
(`push --force-with-lease` sur le tip lu, 3 essais), jamais deux claims à zones
qui se chevauchent, aucune entrée d'un autre dev écrasée en silence.

**Limites** : seuls les devs avec `remote_claims` sont protégés (le hook Stop
avertit si la ref existe sans le flag) ; un doublon sémantique (titre et zone très
différents) n'est pas détectable par script — Claude juge la liste de titres ;
claim périmé jusqu'à 8 h si crash sans `release` (TTL calculé sur `ts`, approximatif
si les horloges dérivent) ; droit de push sur le remote requis ; hors ligne = mode
souple (avertissement, claim non publié) ; ne protège pas des conflits de merge de
code.

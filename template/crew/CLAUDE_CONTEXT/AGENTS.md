# Guide global — invariants produit + anti-patterns

Guide de contexte étendu, lu uniquement quand une règle cross-stack est
ambiguë (sinon lire l'`AGENTS.md` du subtree concerné suffit). À remplir au
fil du projet avec les invariants qui ne sont écrits nulle part ailleurs :
décisions produit qui ne se déduisent pas du code, pièges déjà rencontrés,
anti-patterns à ne pas réintroduire.

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

# Configuration crew du projet

Fichier appartenant au projet : `/crew-update` ne le modifie jamais. Lignes
`clé : valeur`, éditables librement.

## Claims distants (plusieurs devs sur le même repo)

Synchronise en quasi temps réel « qui travaille sur quoi » et les tâches `TODO/`
créées, via la ref git `refs/crew/claims` (poussée seule, jamais sur `main`).
À activer quand plusieurs personnes lancent `/crew-start` sur le même dépôt ;
chacun doit l'activer pour être protégé. Détails : `crew/CLAUDE_CONTEXT/AGENTS.md`.

remote_claims : false

Remote git utilisé pour la ref (défaut : `origin`) :

claims_remote : origin

Ref portant les claims (défaut : `refs/crew/claims`). Si ton serveur git refuse les
refs personnalisées, décommente pour un repli sur une branche dédiée :

# claims_ref : refs/heads/crew-claims

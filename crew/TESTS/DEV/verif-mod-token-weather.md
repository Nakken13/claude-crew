# verif-mod-token-weather

Validation en session réelle du mod `token-weather` (voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md`).
Pas de pendant IA : la suite unitaire (`claude plugin test .`) couvre déjà seuils et cas limites.

Prérequis : `claude plugin disable crew-mates` (copie installée périmée), puis
`claude --plugin-dir .` depuis le worktree/checkout contenant le code ; `claude plugin enable crew-mates` après.

## 🖱️ Manuel / session réelle (DEV)

- [ ] 🖱️ Palier ⛅ Cloudy : atteindre 50-74 % de contexte (`/context`) et vérifier `⛅ Cloudy`, pourcentage identique à `session.usage()`.
- [ ] 🖱️ Palier ⛈️ Storm : 75-89 % → `⛈️ Storm`, et vérifier la bascule exacte au franchissement de 75 %.
- [ ] 🖱️ Palier 🚨 Compact soon : ≥ 90 % → libellé + toast « Fenêtre de contexte à N% » une seule fois.
- [ ] 🖱️ Retour sous 75 % (après `/compact` ou `/clear`) : bandeau redescend et le toast peut se redéclencher.
- [ ] 🖱️ Largeur de terminal étroite : le pourcentage reste lisible (aujourd'hui tronqué, cf. `PROBLEMS/token-weather-reste-a-0-pourcent-session-reelle.md`).

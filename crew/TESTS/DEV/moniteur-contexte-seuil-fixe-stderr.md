# moniteur-contexte-seuil-fixe-stderr

## 🖱️ Manuel (DEV)

- [ ] 🖱️ Session réelle Claude Code > 150k (fenêtre 200k) : l'alerte `[contexte]` s'affiche
      dans l'UI (rendu `systemMessage`), une seule fois jusqu'à +50k.
- [ ] 🖱️ Session `[1m]` : pas d'alerte à 150k, alerte vers 800k (vérifier que le transcript
      réel porte bien le suffixe `[1m]` dans `message.model` ; sinon faux positif 150k connu).

## 🤖 / 🔍 Auto (IA)

Voir `crew/TESTS/IA/moniteur-contexte-seuil-fixe-stderr.md`.

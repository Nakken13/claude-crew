# readme-github-discoverability

Validation des corrections de découvrabilité GitHub / copy du README et
CONTRIBUTING.md (voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 `python check_placeholders.py` ne remonte plus de placeholder non
      résolu dans `CONTRIBUTING.md`.
- [ ] 🔍 Grep sur `README.md` et `CONTRIBUTING.md` : aucune occurrence
      restante de `Nakken13/organized` (seule `Nakken13/claude-crew` doit
      apparaître).
- [ ] 🔍 Le badge GitHub stars n'apparaît plus dans le bloc de badges du
      haut du `README.md` (avant `## 🧩 The problem`) mais apparaît une
      fois en bas, dans la section `## 🤝 Contributing`.
- [ ] 🔍 Le CTA "star ce repo" apparaît deux fois dans `README.md` : une
      fois juste après `## 🧩 The problem`, une fois en fin de fichier —
      les deux formulations sont distinctes (pas de copier-coller
      identique).

# crew-dashboard

Validation du dashboard web local — items nécessitant vraiment une action
humaine (non outillables depuis une session Claude). Voir aussi
`crew/TESTS/IA/crew-dashboard.md` pour le reste.

## 🖱️ Manuel (DEV)

- [ ] 🖱️ Double-cliquer `crew/dashboard.bat` **hors session Claude** (aucune
      variable `CLAUDE_PLUGIN_ROOT` dans l'environnement) et confirmer qu'il
      bootstrap son propre venv à la racine du projet, installe les
      dépendances, lance le serveur et affiche l'URL — inobservable depuis
      une session Claude Code, qui a toujours `CLAUDE_PLUGIN_ROOT` défini.
- [ ] 🖱️ Jugement visuel subjectif : layout/lisibilité du dashboard sur un
      écran réel (espacement, contraste, lisibilité des badges stale/actif),
      au-delà du simple rendu sans erreur déjà vérifié côté IA.
- [ ] 🖱️ Utiliser réellement le bouton "Purger" en interface sur une session
      légitimement périmée (pas de scénario jetable) pour confirmer le
      `confirm()` JS et le retour visuel sont clairs pour un humain.

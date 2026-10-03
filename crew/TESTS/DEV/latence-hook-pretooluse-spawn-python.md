# latence-hook-pretooluse-spawn-python

## 🖱️ Manuel (DEV)

- [ ] 🖱️ Deux vraies sessions Claude (principal + worktree de batch) : la 2e session qui
      `/crew-start` arme `.gate_armed` dans les deux checkouts ; l'édition dans la zone verrouillée
      de l'autre session est bloquée (exit 2) ; fin de session → marqueurs retirés.
- [ ] 🖱️ Fermer une session (SessionEnd synchrone) : son verrou disparaît de `crew_lock.json`.

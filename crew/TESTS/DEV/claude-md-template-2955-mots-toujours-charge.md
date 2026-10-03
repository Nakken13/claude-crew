# claude-md-template-2955-mots-toujours-charge

## 🖱️ Manuel (DEV)

- [ ] 🖱️ Dans un projet dérivé neuf (`/crew-init`) : une session respecte toujours le routage `manager`/personas
      et l'anti-collision avec le CLAUDE.md allégé (pas de régression de comportement perçue).
- [ ] 🖱️ `/crew-update` sur un projet dont le `CLAUDE.md` est personnalisé : fichier en `conflict`, jamais
      écrasé, « version allégée disponible » signalé.
- [ ] 🖱️ Décider quoi faire de `~/.claude/templates/project-scaffold/CLAUDE.md` (source du check
      `verify_plugin_package.py`) : le resynchroniser sur `template/CLAUDE.md` ou l'ignorer.

## 🤖 / 🔍 Auto (IA)

Voir `crew/TESTS/IA/claude-md-template-2955-mots-toujours-charge.md`.

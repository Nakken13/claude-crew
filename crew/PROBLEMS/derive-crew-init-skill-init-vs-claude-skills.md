# Dérive `.claude/skills/crew-init/SKILL.md` vs `skills/crew-init/SKILL.md`

Statut : 🔴 ouvert

`skills/crew-init/SKILL.md` (source packagée plugin, à jour) ne copie plus
dans le projet cible que `CLAUDE.md`, `AGENTS.md`, `PRODUCT.md`,
`CONTRIBUTING.md`, `SECURITY.md`, `check_placeholders.py` et la structure
vide de `crew/` — skills, agents et hooks tournent depuis
`${CLAUDE_PLUGIN_ROOT}` depuis le repackaging plugin (`marketplace-plugin.md`,
clos le 2026-08-22).

`.claude/skills/crew-init/SKILL.md` (copie locale utilisée par ce repo
lui-même en dogfooding) décrit encore l'ancien flux pré-plugin : copie de
`.claude/agents/`, `.claude/skills/crew-*` et fusion `.gitignore`/
`.claude/settings.json` dans le projet cible. Découvert en implémentant
`mecanisme-mise-a-jour-scaffold-multi-projets.md` — le skill `crew-update` a
besoin de savoir lequel des deux flux `crew-init` a réellement suivi pour un
projet donné, et la dérive rend ce choix ambigu si on lit uniquement
`.claude/skills/crew-init/SKILL.md`.

Impact : un utilisateur qui lit `.claude/skills/crew-init/SKILL.md` dans ce
repo (plutôt que `skills/crew-init/SKILL.md`) verrait une procédure obsolète.
Contrairement à `crew-start`/`crew-close-task`/`crew-status` (resynchronisés
à chaque tâche qui les touche, cf. `HISTORIQUE.md` — `worktree-batch-isolation`
notamment), `crew-init` n'a pas suivi le même entretien depuis le
repackaging plugin.

Pistes (non tranchées) : soit resynchroniser `.claude/skills/crew-init/
SKILL.md` sur la version plugin (mais alors ce repo, qui a été bootstrapé
avant le plugin, perd la description du flux qu'il a réellement suivi) ;
soit assumer que `.claude/skills/crew-init/SKILL.md` documente
volontairement le mode legacy et le renommer/clarifier en ce sens.

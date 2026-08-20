# claude-crew as a Claude Code marketplace plugin

**Statut :** 🟡 en cours (spec générée le 20/08/2026)
**Spec :** `docs/superpowers/specs/2026-08-20-marketplace-plugin-design.md`

## Description

Tâche créée automatiquement depuis la spec superpowers. Voir la spec pour le contexte complet.

## Actions

- [ ] `template/` : copier `~/.claude/templates/project-scaffold/*` dans le
      repo (`CLAUDE.md`, `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`,
      `SECURITY.md`, `check_placeholders.py`, `crew/` avec README+INDEX
      vides par dossier, sans fichiers de tâches). Ce repo devient source de
      vérité.
- [ ] `skills/` : déplacer `.claude/skills/crew-*/SKILL.md` vers `skills/`
      (racine plugin).
- [ ] `agents/` : déplacer `.claude/agents/*.md` vers `agents/`.
- [ ] `scripts/` : déplacer `crew/crew_hook.py` et `crew/spec_to_task_hook.py`
      vers `scripts/`.
- [ ] `hooks/hooks.json` : déclarer Stop+SessionEnd →
      `${CLAUDE_PLUGIN_ROOT}/scripts/crew_hook.py`, PostToolUse(Write) →
      `${CLAUDE_PLUGIN_ROOT}/scripts/spec_to_task_hook.py`. Ne pas inclure
      les hooks graphify (spécifiques au dogfooding de ce repo).
- [ ] `.claude-plugin/plugin.json` : manifest (name `claude-crew`, version
      `0.1.0`, description, author, license MIT, homepage).
- [ ] `.claude-plugin/marketplace.json` : entrée marketplace mono-plugin,
      source `.`.
- [ ] Réécrire `skills/crew-init/SKILL.md` : source = `${CLAUDE_PLUGIN_ROOT}/template/`
      au lieu de `~/.claude/templates/project-scaffold/`. Copie uniquement
      les fichiers racine + `crew/` vide — plus les skills/agents/hooks
      (fournis par le plugin). Détecter `${CLAUDE_PLUGIN_ROOT}` absent →
      message "installe le plugin d'abord" au lieu d'un échec silencieux.
- [ ] Vérifier/adapter `skills/crew-new-task`, `crew-close-task`,
      `crew-status`, `crew-start` : aucune logique à changer a priori,
      confirmer qu'aucun ne référence un chemin `.claude/...` local devenu
      obsolète.
- [ ] Tests 🤖 : `check_placeholders.py` exit 0 après `crew-init` sur un
      scratch dir ; `hooks/hooks.json` JSON valide + chemins scripts
      existants ; `crew-init` avec `${CLAUDE_PLUGIN_ROOT}` absent → message
      d'erreur clair (pas de copie partielle) ; diff `template/` vs export
      frais de `~/.claude/templates/project-scaffold/` → aucune dérive.
- [ ] Sortir les tests 🖱️ (DEV) : end-to-end `/plugin marketplace add` +
      `/plugin install` + `/crew-init` depuis un profil Claude Code propre.
- [ ] Root repo : `README.md` mentionne l'install via marketplace
      (`/plugin marketplace add Nakken13/claude-crew`) en plus du clone
      manuel actuel.
- [ ] Clôture : historiser dans `crew/CLAUDE_CONTEXT/HISTORIQUE.md`, sortir
      les tests dans `crew/TESTS/IA/` et `crew/TESTS/DEV/`.

# claude-md-template-2955-mots-toujours-charge

Validation du slimming `template/CLAUDE.md` + `CLAUDE.md` et des descriptions des skills `crew-*`.

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 `cmp CLAUDE.md template/CLAUDE.md` identique ; `wc -w template/CLAUDE.md` ≤ 1200.
- [ ] 🔍 Chaque `§ <titre>` cité dans `skills/*/SKILL.md`, `agents/*.md` et `scripts/crew_hook.py` correspond à un
      titre de `CLAUDE.md` (Batching, Gestion des tâches, 2bis, Personas, Guides AGENTS.md segmentés,
      Efficience de contexte, Routage des skills, graphify).
- [ ] 🔍 Les 8 `description:` de `skills/crew-*/SKILL.md` parsent en YAML, ≤ 40 mots, identiques dans
      `.claude/skills/crew-*/SKILL.md`.
- [ ] 🔍 Checklist d'obligations présentes dans `CLAUDE.md` : états + règle d'or, `manager` au démarrage,
      zones disjointes, clause 1 %, 100 lignes, 150k/100k, `crew/` ancré racine.
- [ ] 🤖 `pytest crew scripts` vert ; `python scripts/dev/verify_plugin_package.py` : aucune erreur nouvelle
      (5 écarts préexistants : CLAUDE.md vs scaffold global, .gitignore, crew-status, manager).
- [ ] 🔍 `skills/crew-update/SKILL.md` ≡ miroir ; section « Cas particulier : CLAUDE.md allégé » présente.

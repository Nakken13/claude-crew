# Listes de personas maintenues à la main + miroirs désynchronisés

Statut : 🔴 ouvert

## Contexte

Ajouter une persona impose d'éditer à la main `ENGINE_FILE_PAIRS`
(`scripts/dev/verify_plugin_package.py`) et `ENGINE_FILES_LEGACY` (dans
**deux** copies : `crew/crew_update.py`, `scripts/crew_update.py`), plus le
compteur « N personas » en prose dans `CLAUDE.md`/`template/CLAUDE.md`.
Relevé par la passe `simplify` (angle altitude) de `persona-legal`.

## Pistes

- `verify_plugin_package.py` : glob `.claude/agents/*.md` vs `agents/*.md`
  — déjà fait sur la branche non mergée `feat/designer-persona`, à récupérer
  au merge plutôt que refaire.
- `ENGINE_FILES_LEGACY` : dériver la partie personas d'un glob (attention au
  contrat « ne jamais écraser silencieusement une personnalisation »).
- Retirer le nombre dans « Cinq personas dédiées ».

## Dérive préexistante sur `main`

`verify_plugin_package.py` échoue : `agents/manager.md` ≠
`.claude/agents/manager.md` et `skills/crew-status/SKILL.md` ≠
`.claude/skills/crew-status/SKILL.md` (commits `790d5c7`, `a509b38` n'ont
mis à jour qu'un côté). Resynchroniser les miroirs.

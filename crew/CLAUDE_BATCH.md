# Batching — workstreams parallèles

Un batch = un Claude. Voir § Batching dans `CLAUDE.md` racine pour les règles
(zone d'impact, invariant de disjonction entre batchs actifs).

## À classer

<Tâches dont la zone d'impact n'est pas encore connue.>

## Batch A

Zone : <fichiers/modules>

- `<slug>.md`

## Batch plugin-packaging

Zone : `template/`, `skills/`, `agents/`, `scripts/`, `hooks/`, `.claude-plugin/`,
`.claude/skills/crew-*`, `.claude/agents/`, `crew/crew_hook.py`,
`crew/spec_to_task_hook.py`, `README.md`, `CONTRIBUTING.md`, `VERSION`,
`CHANGELOG.md`. Fusionné : les 3 tâches touchent toutes `crew_hook.py`
et/ou `crew-init`/`README.md` — zones qui se chevauchaient dans 2 batchs
séparés, regroupées ici (séquencées, un seul Claude à la fois sur cette
zone).

1. `marketplace-plugin.md` (active, `crew/CURRENT_TASKS/`) — repackage en
   plugin ; déplace `crew_hook.py`/`spec_to_task_hook.py` vers `scripts/`,
   réécrit `crew-init`.
2. `hook-auto-commit-cloture-tache.md` — étend `crew_hook.py` **dans son
   nouvel emplacement** `scripts/crew_hook.py` une fois (1) fusionné.
3. `mecanisme-mise-a-jour-scaffold-multi-projets.md` — implémente le flux
   de mise à jour ; le packaging plugin de (1) est un prérequis naturel
   (update = `claude plugin update`), donc après (1). Peut être réordonné
   avant (2) si (2) n'est pas encore prioritaire.


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

1. ~~`marketplace-plugin.md`~~ — repackage en plugin ; déplace
   `crew_hook.py`/`spec_to_task_hook.py` vers `scripts/`, réécrit
   `crew-init`. Clos le 22/08/2026 (code fait depuis le 20/08, clôture crew
   rétroactive — voir `HISTORIQUE.md`), au passage fixé une réf. obsolète
   dans `crew-new-task/SKILL.md` (`.claude/agents/manager.md` → couvre
   aussi `agents/manager.md` fourni par le plugin).
2. `hook-auto-commit-cloture-tache.md` — étend `crew_hook.py` **dans son
   nouvel emplacement** `scripts/crew_hook.py` une fois (1) fusionné.
3. `mecanisme-mise-a-jour-scaffold-multi-projets.md` — implémente le flux
   de mise à jour ; le packaging plugin de (1) est un prérequis naturel
   (update = `claude plugin update`), donc après (1). Peut être réordonné
   avant (2) si (2) n'est pas encore prioritaire.
4. ~~`worktree-batch-isolation.md`~~ — spec du 22/08/2026 (isolation par git
   worktree par batch + gate PreToolUse renforcé `Edit|Write|MultiEdit|
   Bash`). Clos le 22/08/2026 — voir `HISTORIQUE.md`. Zone chevauchait
   `crew_hook.py`, `scripts/`, `.claude/skills/crew-*`, `hooks/hooks.json`,
   `.claude/settings.json` — même zone que (1)-(3), avait rejoint ce batch
   au lieu d'un batch parallèle.
5. `fix-worktree-gitmv-lock-registration-gap.md` — bug de dogfooding sur
   (4) : `gate_pretooluse` (`crew_hook.py`) n'enregistre pas le verrou live
   au moment du `git mv` TODO→CURRENT_TASKS quand il est exécuté depuis un
   worktree de batch (le Stop hook, ROOT-anchored, ne voit jamais ce
   déplacement). Même fichier que (2)-(4), placée en dernier car (2)
   `hook-auto-commit-cloture-tache.md` est actuellement EN COURS
   (`crew/CURRENT_TASKS/`) sur ce même batch — séquencée après, pas de
   conflit de zone (même batch, pas de nouveau batch parallèle).


# Batching — workstreams parallèles

Un batch = un Claude. Voir § Batching dans `CLAUDE.md` racine pour les règles
(zone d'impact, invariant de disjonction entre batchs actifs).

## Batch A — Audit ECC : tokens & réactivité du plugin

Zone : `scripts/crew_hook.py`, `crew/crew_hook.py`, `crew/test_crew_hook.py`,
`hooks/hooks.json`, `scripts/dev/verify_plugin_package.py`, `template/.gitignore`,
`.gitignore`, `README.md`, `CLAUDE.md`, `template/CLAUDE.md`, `skills/crew-*/SKILL.md`,
`.claude/skills/crew-*/SKILL.md`, `scripts/crew_update.py`,
`crew/CLAUDE_CONTEXT/HISTORIQUE.md`

Un seul Claude, tâches **dans l'ordre** (chaque tâche modifie le hook ou un
fichier touché par la suivante ; la dernière dépend du contenu ajouté par 3 et 4).
Prérequis commun avant la première : repo resynchronisé avec `origin/main`
(dérive signalée par l'audit `docs/audits/2026-10-01-audit-ecc-vs-claude-crew.md`).

1. `faux-positif-check-batches-claude-md.md` — quick win, parser `TASK_LINE_RE`.
2. `latence-hook-pretooluse-spawn-python.md` — marqueur `.gate_armed` + pré-filtre
   shell + `async` SessionEnd/PostToolUse. Dépend de 1 (même fonction de scan,
   mêmes tests).
3. `moniteur-contexte-seuil-fixe-stderr.md` — `systemMessage`, seuil scalé, palier
   50k. Touche la sortie JSON Stop (après 2 : stabiliser `hooks.json` d'abord).
4. `continuite-session-sessionstart-precompact.md` — hook `SessionStart` + digest ;
   réutilise `check_batches()` corrigé en 1 et la forme de `hooks.json` issue de 2.
5. `claude-md-template-2955-mots-toujours-charge.md` — slimming, **EN DERNIER** :
   reprend la formulation § Reset de session écrite en 3 et l'étape 1 de
   `crew-start` réécrite en 4 ; chevauche 3 (`CLAUDE.md`/`template/CLAUDE.md`) et 4
   (`skills/crew-start/SKILL.md` + miroir), donc même batch et pas de batch parallèle.

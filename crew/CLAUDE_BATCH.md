# Batching — workstreams parallèles

Un batch = un Claude. Voir § Batching dans `CLAUDE.md` racine pour les règles
(zone d'impact, invariant de disjonction entre batchs actifs).


## Batch 1 — Vérification réelle des mods hooks

Zone : `hooks/mods/**`, `hooks/mods.test.ts`, `hooks/register.ts`

Séquence ordonnée (socle partagé d'abord, du plus simple au plus couplé) :

1. `verif-mod-token-weather.md`
2. `verif-mod-prompt-cache-control.md`
3. `verif-mod-crew-radar.md`
4. `verif-mod-batch-progress.md`
5. `verif-mod-batch-eta-cost.md`
6. `verif-mod-file-lock-monitor.md`
7. `verif-mod-agent-flow.md`
8. `verif-mod-turn-inspector.md`
9. `verif-mod-stack-viewer.md`
10. `verif-mod-batch-dependency-graph.md`

Note : `shared.ts` n'a pas de tâche dédiée, il est couvert par chaque tâche (dépendance commune) ; modifs non committées en cours sur mods.test.ts, crew-radar, prompt-cache-control, shared.

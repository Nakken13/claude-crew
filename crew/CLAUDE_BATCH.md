# Batching — workstreams parallèles

Un batch = un Claude. Voir § Batching dans `CLAUDE.md` racine pour les règles
(zone d'impact, invariant de disjonction entre batchs actifs).

## Batch A — Audit ECC : tokens & réactivité du plugin

Zone : `scripts/crew_hook.py`, `crew/crew_hook.py`, `crew/test_crew_hook.py`,
`hooks/hooks.json`, `scripts/dev/verify_plugin_package.py`, `template/.gitignore`,
`.gitignore`, `README.md`, `CLAUDE.md`, `template/CLAUDE.md`, `skills/crew-*/SKILL.md`,
`.claude/skills/crew-*/SKILL.md`, `scripts/crew_update.py`, `crew/crew_update.py`,
`crew/test_crew_update.py`, `crew/CLAUDE_CONTEXT/HISTORIQUE.md`,
`scripts/dashboard/server.py`, `scripts/dashboard/test_server.py`

Un seul Claude, tâches **dans l'ordre** (chaque tâche modifie le hook ou un
fichier touché par la suivante ; la dernière dépend du contenu ajouté par 6 et 7).
Prérequis commun avant la première : repo resynchronisé avec `origin/main`
(dérive signalée par l'audit `docs/audits/2026-10-01-audit-ecc-vs-claude-crew.md`).
Numérotation entière obligatoire (le parser `TASK_LINE_RE` du hook ne reconnaît que
`\d+.`) — 1 à 3 = lot « désynchro du verrou » (voyageo/time2cook), suite de 0.

0. ~~`fix-zone-overlap-faux-positifs.md`~~ — `check_zone_overlaps` ne compte que les
   batchs réellement en cours (pas TODO) ; 3e session non bloquée.
1. ~~`verrou-partage-worktrees.md`~~ — `crew_lock.json` + mutex centralisés dans le
   checkout principal (`_resolve_main_root` sans spawn git), migration du lock local
   legacy. **Avant 5** : change l'emplacement du verrou, donc du marqueur
   `.gate_armed` que 5 introduit (à poser dans le principal ET chaque worktree
   enregistré).
2. ~~`identite-batch-sans-statut.md`~~ — clé de batch = header tronqué au premier ` · ` ;
   lock, comparaisons, slug worktree/branche (+ `crew-start`). Après 1 : touche
   `_worktree_paths_for` que 1 fait passer sur `MAIN_ROOT.name`.
3. ~~`detecter-double-hook-projet-cible.md`~~ — `crew_update.py` (+ copie) avertit si
   plugin actif ET hooks locaux `crew/crew_hook.py` dans `.claude/settings.json`.
   Indépendante du code du hook, placée ici pour clore le lot « désynchro verrou » ;
   partage `skills/crew-*/SKILL.md` avec 7/8.
4. ~~`faux-positif-check-batches-claude-md.md`~~ — quick win, parser `TASK_LINE_RE`.
5. ~~`latence-hook-pretooluse-spawn-python.md`~~ — marqueur `.gate_armed` + pré-filtre
   shell + `async` SessionEnd/PostToolUse. Dépend de 4 (même fonction de scan,
   mêmes tests) et de 1 (emplacement du verrou).
6. `moniteur-contexte-seuil-fixe-stderr.md` — `systemMessage`, seuil scalé, palier
   50k. Touche la sortie JSON Stop (après 5 : stabiliser `hooks.json` d'abord).
7. `continuite-session-sessionstart-precompact.md` — hook `SessionStart` + digest ;
   réutilise `check_batches()` corrigé en 4 et la forme de `hooks.json` issue de 5.
8. `claude-md-template-2955-mots-toujours-charge.md` — slimming, **EN DERNIER** :
   reprend la formulation § Reset de session écrite en 6 et l'étape 1 de
   `crew-start` réécrite en 7 ; chevauche 6 (`CLAUDE.md`/`template/CLAUDE.md`) et 7
   (`skills/crew-start/SKILL.md` + miroir), donc même batch et pas de batch parallèle.

# `template/CLAUDE.md` : 2955 mots chargés dans chaque session

Statut : 🟡 en cours — tâche : `crew/TODO/claude-md-template-2955-mots-toujours-charge.md` (Batch A, cf. `crew/CLAUDE_BATCH.md`)

## Constat

`template/CLAUDE.md` pèse 2955 mots (~4k tokens), injectés dans **chaque**
session de **chaque** projet bootstrapé. Répartition par section :

- routage skills : 697 mots
- cycle de vie des tâches : 910
- efficience de contexte : 457
- personas : 405
- batching : 396
- commandes `/crew-*` : 248
- graphify : 143

Une partie est redondante avec les skills `crew-*`, qui encodent déjà la
procédure (cycle de vie, batching, clôture). Les descriptions frontmatter des
8 skills font 337-601 caractères chacune (le `context-budget` d'ECC considère
> 30 mots comme du bloat). Comparaison ECC : CLAUDE.md d'environ 600 mots, le
reste dans des skills chargés à l'invocation.

## Impact

- Occupe la fenêtre de contexte dès le premier tour et avance la compaction.
- Coût fixe multiplié par le nombre de sessions et de projets dérivés.
- Risque inverse à arbitrer : une règle sortie du contexte permanent
  (routage personas obligatoire, anti-collision avant démarrage) peut ne plus
  être suivie si elle n'est chargée qu'à l'invocation d'un skill.

## Pistes

- Déplacer les sections procédurales (cycle de vie détaillé, batching,
  commandes) vers les skills `crew-*` correspondants ; ne garder dans
  `CLAUDE.md` que les invariants et les règles de routage.
- Raccourcir les descriptions frontmatter des skills (cible ~30 mots).
- Mesurer avant/après (tokens au premier tour) pour objectiver le gain.
- Arbitrage « quoi garder en permanent vs à l'invocation » en cours côté
  persona `architect` : ne pas trancher ici.

Source : audit ECC vs claude-crew du 2026-10-01

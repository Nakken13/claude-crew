# Fix `check_batches()` : ne parser que les lignes de liste (faux positif `CLAUDE.md`)

Zone d'impact : `scripts/crew_hook.py`, `crew/crew_hook.py` (copie synchronisée),
`crew/test_crew_hook.py`.
Source : `crew/PROBLEMS/faux-positif-check-batches-claude-md.md` — audit
`docs/audits/2026-10-01-audit-ecc-vs-claude-crew.md` § 5.2. Arbitrage `architect` : rendu.

## Description

`check_batches()` extrait les refs de tâches avec la regex générique
`` `([\w\-.]+\.md)` `` sur tout `CLAUDE_BATCH.md`, donc la prose d'en-tête
(« Voir § Batching dans `CLAUDE.md` ») produit « référence une tâche inexistante :
`CLAUDE.md` » dans chaque projet bootstrapé. Remplacer par le parsing de lignes de
liste via `TASK_LINE_RE` (déjà utilisé par `_task_line_counts`/`prune_closed_batches`).
Quick win, première tâche du batch.

## Actions

- [ ] Vérifier que le repo local est synchronisé avec `origin/main` (`git status`,
      `git fetch` ; l'audit signale une dérive) avant de toucher au hook.
- [ ] TDD rouge : ajouter dans `crew/test_crew_hook.py` un test où `CLAUDE_BATCH.md`
      contient l'en-tête du template (« `CLAUDE.md` » en prose) + une ligne `Zone :`
      citant un `.md` + une vraie tâche listée → `check_batches()` ne doit émettre
      aucun warning « inexistante » pour `CLAUDE.md` ni pour le `.md` de la Zone.
      Lancer, constater l'échec.
- [ ] TDD vert : dans `scripts/crew_hook.py`, remplacer le `re.findall` générique
      sur les backticks par un parcours `TASK_LINE_RE.finditer(text)` (groupe 2 =
      slug ; ignorer les refs barrées via groupes 1/3 ou garder le `re.sub(~~...~~)`
      existant). Les placeholders `<...>.md` restent ignorés. Docstring mise à jour.
- [ ] Test de non-régression : une tâche réellement disparue, listée sur une ligne
      de liste `- `slug.md``, déclenche toujours « référence une tâche inexistante » ;
      une tâche TODO absente du fichier déclenche toujours « non catégorisée ».
- [ ] Synchroniser `crew/crew_hook.py` avec `scripts/crew_hook.py` (copie identique),
      puis `python scripts/dev/verify_plugin_package.py` vert et
      `python -m pytest crew/test_crew_hook.py` vert.
- [ ] Vérifier sur ce repo que le hook Stop n'émet plus l'avertissement
      `[batch] ... CLAUDE.md` (lancer le hook à la main avec un payload Stop minimal).

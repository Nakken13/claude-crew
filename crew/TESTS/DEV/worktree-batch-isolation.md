# worktree-batch-isolation

Validation de l'isolation physique par `git worktree` par batch actif +
du gate `PreToolUse` durci (voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md`). Le
pendant automatisable est dans `../IA/worktree-batch-isolation.md`.

## 🖱️ Manuel / multi-session réelle (DEV)

- [ ] 🖱️ Ouvrir deux vrais terminaux, chacun avec sa propre session Claude
      Code. Lancer `/crew-start` sur deux batches différents (zones non
      chevauchantes) en même temps — vérifier que chaque session travaille
      bien dans son propre worktree `../<repo>-batch-<slug>/` (pas dans le
      checkout principal), et qu'aucun fichier de l'une n'apparaît modifié
      côté de l'autre pendant que les deux tournent en parallèle.
- [ ] 🖱️ Clôturer les deux tâches (`/crew-close-task`) : confirmer un merge
      propre (fast-forward) pour les deux, la suppression des deux
      worktrees + branches, et que `crew/CLAUDE_CONTEXT/crew_lock.json` ne
      contient plus aucune des deux sessions.
- [ ] 🖱️ Provoquer volontairement un conflit (modifier le même fichier hors
      des deux zones de batch, sur `main`, entre les deux `/crew-start` et
      les deux `/crew-close-task`) et vérifier que le rebase d'au moins une
      des deux branches échoue proprement (`git rebase --abort` automatique,
      worktree + branche conservés, conflit signalé) plutôt que de fusionner
      silencieusement une perte de contenu.

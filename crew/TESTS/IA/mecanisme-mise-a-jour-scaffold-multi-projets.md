# mecanisme-mise-a-jour-scaffold-multi-projets

Validation du mécanisme `/crew-update` (mise à jour des fichiers "moteur"
d'un projet déjà bootstrapé) — voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md` et
`crew/crew_update.py`/`crew/test_crew_update.py`.

## 🤖 / 🔍 Auto (IA)

- [x] 🤖 `python -m pytest crew/test_crew_update.py -v` → 23 tests passent
      (tmp_path isolé par test, fichiers réels, aucun mock) : les 5 statuts
      de `classify()` (`absent`/`new`/`removed`/`up_to_date`/`apply`/
      `conflict`), `plan()`/`apply()` ne touchent jamais `crew/TODO/` ni
      `crew/CLAUDE_CONTEXT/HISTORIQUE.md`, un fichier `conflict` n'est jamais
      écrasé, un fichier `removed` (disparu de la source) ne fait jamais
      planter `apply()`, `record_version()` ne bump le hash que des fichiers
      réellement appliqués, `seed()` amorce une baseline et refuse de
      l'écraser sans `force=True`, `detect_mode()` distingue legacy/plugin.
- [x] 🤖 `python -m pytest crew/ -q` → suite complète 36 passed (le fichier
      annonçait 31, décalage doc suite aux 5 nouveaux tests
      `test_gate_pretooluse_git_mv_*` ajoutés depuis — aucune régression,
      0 échec), aucune régression sur `crew/test_crew_hook.py`.
- [x] 🔍 `python scripts/dev/verify_plugin_package.py` → PASS (8 checks,
      dont le nouveau `check_crew_scripts_copied` et la paire
      `crew-update` dans `ENGINE_FILE_PAIRS`) ; `crew/crew_update.py` et
      `scripts/crew_update.py` restent byte-identiques, de même que
      `skills/crew-update/SKILL.md` et `.claude/skills/crew-update/SKILL.md`.
- [ ] 🔍 Simulation end-to-end en CLI directe (sans passer par le skill) sur
      un dossier `tmp` factice : créer un "projet source" et un "projet
      cible" v1 avec un `CLAUDE.md` divergent, lancer
      `python crew/crew_update.py --project <cible> --source <source>
      --seed --source-version 1.0.0` (amorçage), puis modifier le
      `CLAUDE.md` source, relancer sans `--seed` (dry-run) → doit lister
      `apply` pour `CLAUDE.md` ; relancer avec `--apply --source-version
      2.0.0` → fichier mis à jour, `crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json`
      bumpé à `2.0.0`. Personnaliser ensuite le fichier cible et relancer →
      doit ressortir `conflict`, fichier inchangé après `--apply`.
- [ ] 🔍 Invoquer réellement `/crew-update` (skill) sur ce repo lui-même
      (mode `legacy` attendu, `.claude/skills/crew-init/SKILL.md` présent) —
      vérifier que le résumé par statut est affiché, qu'`AskUserQuestion` est
      posée avant toute écriture, et qu'aucun fichier sous `crew/TODO/`,
      `crew/CURRENT_TASKS/`, `crew/PROBLEMS/`, `crew/ICEBOX/`, `crew/TESTS/`
      ou `crew/CLAUDE_CONTEXT/HISTORIQUE.md` n'apparaît dans le rapport.

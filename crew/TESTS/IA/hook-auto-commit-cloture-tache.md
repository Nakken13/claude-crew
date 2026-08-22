# hook-auto-commit-cloture-tache

Validation du commit git auto local (jamais de push) déclenché à la clôture
réelle d'une tâche crew — voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md` et
`crew/test_crew_hook.py`.

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py -v` → 8 tests passent
      (dépôt git temporaire isolé par test, aucun mock sur git/subprocess) :
      commit créé avec scope + message corrects ; commit ignoré quand
      `crew/CLAUDE_CONTEXT/BATCH_LOCKS.md` (gitignoré, régénéré sur disque)
      est présent ; fichier utilisateur déjà stagé hors `crew/` jamais
      embarqué et reste stagé après ; détection par slug (2 tâches finies le
      même tour, une seule vraiment historisée → seule celle-ci est
      committée) ; idempotence (2e appel sans nouvelle clôture → aucun
      nouveau commit) ; échec `pre-commit` avalé sans lever d'exception ;
      no-op si `finished` vide ; no-op si `finished` non vide mais
      HISTORIQUE.md pas touché.
- [ ] 🔍 Dans le vrai dépôt (pas un fixture) : clore une tâche réelle (petite,
      jetable) via le cycle normal, vérifier `git log -1` → commit
      `chore(crew): cloture tache <slug>` scopé exactement aux fichiers
      `crew/` attendus (`git show --stat HEAD`), aucun fichier hors `crew/`,
      aucun push effectué.
- [ ] 🔍 `python scripts/dev/verify_plugin_package.py` → PASS, `crew/
      crew_hook.py` et `scripts/crew_hook.py` restent synchronisés (diff nul
      hors la divergence `ROOT`/`CLAUDE_PROJECT_DIR` déjà documentée).

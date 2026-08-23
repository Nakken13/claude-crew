# Plugin marketplace packaging

- [x] 🤖 `python template/check_placeholders.py` sur un `crew-init` frais
      (scratch dir) → exit 0, aucun placeholder `<...>` non résolu.
- [x] 🔍 `hooks/hooks.json` : JSON valide (`python -c "import json;
      json.load(open('hooks/hooks.json'))"`) et chaque `command` référence
      un script existant dans `scripts/`.
- [x] 🤖 `crew-init` avec `${CLAUDE_PLUGIN_ROOT}` absent → message d'erreur
      clair ("installe le plugin d'abord"), pas de copie partielle de
      fichiers.
- [x] 🔍 Diff `template/` vs export frais de
      `~/.claude/templates/project-scaffold/` → chaque écart doit
      correspondre à une évolution volontaire post-migration (le repo est
      source de vérité depuis 2026-08-20 ; la copie locale n'est plus
      censée être synchronisée). Vérifier qu'aucun écart n'est une
      régression accidentelle (fichier supprimé par erreur, etc.).

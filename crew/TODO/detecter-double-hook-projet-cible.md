# Détecter un double hook crew (plugin + copie locale) dans un projet cible

Zone d'impact : `scripts/crew_update.py` + `crew/crew_update.py` (copies identiques),
`crew/test_crew_update.py`, `skills/crew-update/SKILL.md` + miroir
`.claude/skills/crew-update/SKILL.md`, éventuellement `skills/crew-status/SKILL.md`
+ miroir.
Source : voyageo (correctif ponctuel fait à la main, hors claude-crew).

## Description

voyageo exécutait DEUX hooks crew sur le même `crew_lock.json` : son
`.claude/settings.json` appelait `$CLAUDE_PROJECT_DIR/crew/crew_hook.py` (copie
locale divergente) ET le plugin claude-crew appelait
`${CLAUDE_PLUGIN_ROOT}/scripts/crew_hook.py` → logiques incohérentes sur le même
état (ex. l'une ignore `PAUSED/`). Garde-fou générique : détecter ce cas et
**avertir + proposer** le retrait des entrées locales, jamais de modification
silencieuse.

## Actions

- [ ] Définir le signal « plugin actif » : `enabledPlugins` contenant `claude-crew`
      dans `.claude/settings.json` / `.claude/settings.local.json` du projet et/ou
      `~/.claude/settings.json` (injectable en test), ou exécution depuis
      `${CLAUDE_PLUGIN_ROOT}` ; consigner le choix dans ce fichier.
- [ ] TDD rouge (`crew/test_crew_update.py`) : `test_detect_double_hook_plugin_and_local`
      (settings avec entrée hook `crew/crew_hook.py` + plugin actif → détecté, liste
      des événements concernés) ; `test_no_double_hook_plugin_only` ;
      `test_no_double_hook_legacy_without_plugin` (legacy sans plugin = normal) ;
      `test_detect_double_hook_tolerates_missing_or_invalid_settings`.
- [ ] Implémenter `detect_double_hook(project_root, …)` pure (lecture JSON, aucune
      écriture) dans `scripts/crew_update.py`, recopiée dans `crew/crew_update.py`.
- [ ] Brancher dans `_main()` : avertissement explicite (événements + commandes
      locales en double) + proposition de retrait ; retrait seulement sur
      confirmation explicite (flag/réponse), test `test_double_hook_not_removed_without_confirmation`.
- [ ] Documenter le cas dans `skills/crew-update/SKILL.md` (+ miroir) ; décider si
      `/crew-status` le signale aussi (lecture seule) et, si oui, l'ajouter à
      `skills/crew-status/SKILL.md` (+ miroir).
- [ ] `diff scripts/crew_update.py crew/crew_update.py` vide ;
      `pytest crew/test_crew_update.py` vert.

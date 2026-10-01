# Continuité de session : hook `SessionStart` injectant un digest crew ≤ 2000 chars

Zone d'impact : `hooks/hooks.json` (nouvelle entrée `SessionStart`), `scripts/crew_hook.py`,
`crew/crew_hook.py` (copie synchronisée), `crew/test_crew_hook.py`,
`skills/crew-start/SKILL.md` + miroir `.claude/skills/crew-start/SKILL.md`,
`scripts/dev/verify_plugin_package.py` (`check_hooks_json` : mapping événement → script),
`README.md` (interrupteur `CREW_SESSION_DIGEST`).
Source : `crew/PROBLEMS/continuite-session-sessionstart-precompact.md` — audit § 4.C.
Arbitrage `architect` : rendu. **Pas de PreCompact** (redondant : `SessionStart`
source `compact` ré-injecte le digest). Vue dérivée, rien n'est écrit dans `crew/`.

## Description

Aucun hook `SessionStart` : chaque reprise relit `crew/` à la main (3-6k tokens
d'outils) et une compaction perd l'état. Ajouter une entrée `SessionStart` (matcher
`startup|resume|compact`) qui fait renvoyer à `crew_hook.py` un
`hookSpecificOutput.additionalContext` plafonné à 2000 caractères, calculé depuis
les fichiers `crew/` existants.

## Actions

- [ ] TDD rouge : tests du nouveau builder de digest (fonction pure prenant les
      données lues) — (a) contenu : CURRENT_TASKS puis PAUSED (slug, titre, `n/m`
      cases via `_task_line_counts` ou équivalent sur le fichier de tâche), batchs
      actifs + `Zone :`, verrous d'autres sessions (après purge des sessions mortes),
      3 derniers titres `## ` de `HISTORIQUE.md`, warnings `check_batches()` ;
      (b) ordre fixe : CURRENT/PAUSED avant batchs avant verrous avant HISTORIQUE ;
      (c) plafond : avec 20 tâches factices, sortie ≤ 2000 chars, troncature
      annoncée (« … (+N) »), les sections de tête jamais sacrifiées au profit de
      HISTORIQUE ; (d) `crew/` vide → digest d'une ligne, pas d'exception.
- [ ] TDD vert : implémentation dans `crew_hook.py`, branche
      `hook_event_name == "SessionStart"` → stdout JSON
      `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`,
      exit 0. Lecture seule : aucun `write_text`/`save_locks` sur ce chemin (test qui
      vérifie que `crew/` est inchangé après l'appel).
- [ ] Interrupteur `CREW_SESSION_DIGEST=off` → sortie vide immédiate ; test + une
      ligne dans `README.md`.
- [ ] `hooks/hooks.json` : entrée `SessionStart`, matcher `startup|resume|compact`,
      même commande Python que les autres événements, `timeout` 10. Pas d'`async`
      (l'`additionalContext` doit être rendu avant le premier tour).
- [ ] `scripts/dev/verify_plugin_package.py` : ajouter `SessionStart` au mapping
      événement → `scripts/crew_hook.py` dans `check_hooks_json` ; script vert.
- [ ] `skills/crew-start/SKILL.md` étape 1 (« Lire l'état ») : remplacer la relecture
      systématique de `crew/` par « lire le digest injecté par le hook SessionStart ;
      vérifier sur fichier avant toute écriture (le digest est une vue, pas la source) ;
      si le digest est absent (`CREW_SESSION_DIGEST=off`, plugin non chargé), relire
      `crew/` comme avant ». Copier à l'identique dans `.claude/skills/crew-start/SKILL.md`
      (contrôlé par `verify_plugin_package.py`).
- [ ] Synchroniser `crew/crew_hook.py` ↔ `scripts/crew_hook.py` ; pytest vert.
- [ ] Mesure : chronométrer le hook SessionStart sur ce repo (un spawn par
      démarrage/reprise/compaction, à reporter dans HISTORIQUE) et vérifier
      manuellement qu'une nouvelle session affiche bien le digest au premier tour.

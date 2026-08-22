# Fix — enregistrement du verrou live manquant pour `git mv` TODO→CURRENT_TASKS depuis un worktree de batch

Bug découvert en dogfooding live la spec
`docs/superpowers/specs/2026-08-22-worktree-batch-isolation-design.md`
(tâche `worktree-batch-isolation`, clôturée le 22/08/2026).

Le hook `crew/crew_hook.py` — event **Stop** — détecte les tâches
« démarrées » (`started`) en diffant `crew/TODO/`/`crew/CURRENT_TASKS/` du
tour précédent vs courant, mais ces chemins sont toujours résolus via `ROOT`
(`pathlib.Path(__file__).resolve().parent.parent`), donc toujours le
**checkout principal**, jamais un worktree. Quand `/crew-start` fait le
`git mv crew/TODO/<slug>.md crew/CURRENT_TASKS/<slug>.md` **depuis un
worktree de batch** (`../<repo>-batch-<slug>/`, exigé par la spec
worktree-batch-isolation), ce déplacement n'existe que dans le worktree — le
checkout principal ne voit aucun changement de `crew/TODO`/`crew/CURRENT_TASKS`.
Résultat : `started` reste vide côté hook Stop pour ce cas, et
`_register_task_lock` (qui alimente `crew_lock.json` — verrou live par
session) n'est donc jamais appelé automatiquement pour ce chemin.

`crew_lock.json` lui-même est correctement partagé (même raisonnement
ROOT-anchored → toujours le fichier du checkout principal, un seul fichier
partagé entre worktrees, pas de duplication) — seul le **déclenchement
automatique** de l'enregistrement est cassé pour le flux worktree.

Constaté en live : après un `git mv` réel dans
`../claude-crew-batch-plugin-packaging`, `crew/CLAUDE_CONTEXT/crew_lock.json`
n'avait aucune entrée session pour la tâche tant que le marqueur no-op
`: "crew-resume:<slug>.md"` n'a pas été exécuté manuellement (celui-ci
fonctionne car il ne dépend pas du diff TODO/CURRENT_TASKS — juste du texte
de la commande Bash — et déclenche `_claim_resume_lock`/`_register_task_lock`
directement, cf. `crew_hook.py`).

Fichier concerné : `crew/crew_hook.py` (+ resync obligatoire vers
`scripts/crew_hook.py`, copie plugin — même procédure que les rounds
précédents de hardening batch-lock, commits `dffbcdd`, `7800e48`, `5ae46e6`,
`566b2ac`). Fonction à modifier : `gate_pretooluse`, branche `Bash` → `git mv`
(actuellement : valide catégorisation + collision via
`check_batch_collisions`, mais n'écrit rien — le commentaire du docstring dit
explicitement « le chemin git mv n'ecrit rien — la mise a jour de ses
verrous reste au Stop », hypothèse fausse pour le flux worktree).

Ne toucher à aucun fichier hors `crew/` (et sa copie `scripts/crew_hook.py`
resynchronisée par la procédure existante).

## Actions

- [ ] Dans `gate_pretooluse`, branche `git mv` TODO→CURRENT_TASKS
      (`_extract_git_mv_task`) : après la validation collision réussie
      (`check_batch_collisions` ne retourne pas de `reason`), enregistrer
      directement le verrou via
      `_register_task_lock(slug, session_id, locks, now_dt, sections)`
      sous `LocksMutex()` — même schéma que `_claim_resume_lock`.
- [ ] À l'intérieur du mutex : refaire un `load_locks()` +
      `purge_stale_locks()` + **re-vérification de collision fraîche** avant
      d'enregistrer, pour éviter un TOCTOU avec la lecture `locks` externe
      déjà faite plus haut dans `gate_pretooluse` pour le scan générique de
      la même invocation (deux sessions pourraient passer la première
      vérification avant que l'une des deux n'écrive son verrou).
- [ ] Capturer `worktree` (chemin relatif du worktree courant si la commande
      s'exécute depuis un worktree de batch, sinon absent) dans l'entrée
      passée à `_register_task_lock`, cohérent avec ce que fait déjà
      `_claim_resume_lock`/le reste du système pour `crew_lock.json` /
      `BATCH_LOCKS.md` (colonne `worktree`).
- [ ] Devenir préventif (avant exécution du `git mv`) plutôt que rétroactif
      (au Stop suivant), cohérent avec le reste du gate PreToolUse — en cas
      d'échec d'enregistrement (verrou déjà pris par une autre session entre
      la première vérification et le mutex), bloquer via `sys.exit(2)` +
      message stderr, même style que `_claim_resume_lock`.
- [ ] Vérifier si la boucle `started` du Stop hook (dans `main()`) doit
      **rester en fallback** (cas où le `git mv` se fait directement dans le
      checkout principal, sans worktree — toujours possible/légal) ou si
      elle devient totalement redondante une fois le fix ci-dessus en place.
      Ne pas la supprimer sans réflexion explicite ; documenter la décision
      (garder en fallback vs. supprimer) dans le commit ou en commentaire.
- [ ] Vérifier l'idempotence : si `gate_pretooluse` enregistre déjà le
      verrou de façon préventive, s'assurer que le passage ultérieur au Stop
      (si la boucle `started` est conservée en fallback) ne provoque pas de
      double-traitement problématique (écraser le `since` existant, log de
      collision fantôme, etc.) — `_register_task_lock` doit rester
      idempotent pour la même session.
- [ ] Resynchroniser `crew/crew_hook.py` → `scripts/crew_hook.py` (copie
      plugin) une fois le fix validé, même procédure que les rounds
      précédents de hardening batch-lock.
- [ ] Mettre à jour la checklist de test correspondante : si
      `crew/test_crew_hook.py` existe déjà (introduit entre-temps par la
      tâche voisine `hook-auto-commit-cloture-tache.md`), s'y greffer avec un
      scénario couvrant `git mv` depuis un worktree simulé → verrou présent
      immédiatement dans `crew_lock.json` sans attendre le Stop suivant ;
      sinon, ajouter les items correspondants (checklist markdown non
      cochée) dans `crew/TESTS/IA/` (🤖/🔍, scénario scriptable :
      simuler un `git mv` depuis un worktree puis inspecter
      `crew/CLAUDE_CONTEXT/crew_lock.json`) et/ou `crew/TESTS/DEV/` si un
      volet nécessite une vérification manuelle.
- [ ] Vérifier que `crew/CLAUDE_CONTEXT/BATCH_LOCKS.md` (régénéré par le
      hook) reflète bien la tâche verrouillée immédiatement après le `git mv`
      depuis un worktree, sans attendre un tour Stop supplémentaire.

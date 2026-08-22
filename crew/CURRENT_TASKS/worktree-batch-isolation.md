# Worktree isolation + hardened gate for batch anti-collision

**Statut :** 🟡 en cours (spec générée le 22/08/2026)
**Spec :** `docs/superpowers/specs/2026-08-22-worktree-batch-isolation-design.md`
**Batch :** `Batch plugin-packaging` (`crew/CLAUDE_BATCH.md`) — item 4,
séquencée après `marketplace-plugin.md`, `hook-auto-commit-cloture-tache.md`,
`mecanisme-mise-a-jour-scaffold-multi-projets.md` : zone qui chevauche
`crew_hook.py`, `scripts/`, `.claude/skills/crew-*`, `hooks/hooks.json`,
`.claude/settings.json`, `crew/CLAUDE_BATCH.md` avec les 3 tâches déjà dans
ce batch.

## Description

Décline la spec superpowers du 22/08/2026 : isolation physique par git
worktree par batch actif + gate PreToolUse renforcé (`Edit|Write|MultiEdit|
Bash`) pour garantir qu'aucune collision silencieuse n'est possible entre
deux sessions Claude Code lancées en parallèle sur des batches différents
via `/crew-start`. Deux couches défense-en-profondeur : Layer 1 (worktree
= isolation physique, garantie dure) et Layer 2 (gate hardened = filet de
sécurité pour tout ce qui bypass le worktree). Voir la spec complète pour
l'architecture, le format `crew_lock.json`, le data flow et le error
handling détaillés.

## Actions

### `crew_lock.json` (remplace `.batch_locks.json`)
- [ ] Nouveau schéma session→`{batch, tasks, worktree, branch, since}` dans
      `crew/crew_hook.py` (spec § Components > `crew_lock.json`) — une
      entrée par session active, `tasks` imbriqué sous la session au lieu
      d'être la clé top-level.
- [ ] Écriture toujours sous le `LocksMutex` existant (marker file
      `O_CREAT|O_EXCL`, TTL 6h, wait best-effort 2s, ne bloque jamais le
      tour) — mutex inchangé, seul le schéma stocké change.
- [ ] Purge TTL 6h inchangée, mais purge désormais l'entrée session
      entière d'un coup (tasks + worktree ensemble).
- [ ] `BATCH_LOCKS.md` (vue lisible régénérée) : garder le format actuel,
      ajouter une colonne `worktree` quand présente.

### Adaptation des fonctions de collision existantes
- [ ] `check_batch_collisions`, `check_zone_overlaps`,
      `_section_lock_sessions`, `regen_batch_locks_md` : dérivent
      désormais la vue slug→session_id à partir de `sessions[*].tasks` au
      lieu de lire une map plate — logique interne inchangée, seule la
      source de données change (spec § Data flow, point 2).

### Gate `gate_pretooluse` renforcé
- [ ] Matcher étendu `Bash` → `Bash|Edit|Write|MultiEdit`.
- [ ] `Edit`/`Write`/`MultiEdit` : extraction directe de `file_path` depuis
      `tool_input` (pas de parsing shell nécessaire).
- [ ] `Bash` : garder l'extraction `git mv` actuelle
      (`_extract_git_mv_task`), ajouter un scan best-effort générique
      (pas un parseur shell complet, même esprit que l'existant) pour
      `rm`/`mv`/`cp`/redirection `>` repérant un token de chemin sous une
      zone verrouillée.
- [ ] Logique de blocage : chemin sous une `Zone:` verrouillée (dans
      `crew_lock.json`) par une session ≠ appelant → `exit(2)` avec
      message nommant le batch + l'autre session. Zone non déclarée, ou
      verrou vide/tenu par la même session → laisser passer (fail-open
      inchangé, cohérent avec le comportement actuel).

### Config hooks
- [ ] `hooks/hooks.json` (côté plugin) : élargir le matcher `PreToolUse` à
      `Bash|Edit|Write|MultiEdit`.
- [ ] `.claude/settings.json` (local, ce repo) : même élargissement.

### `/crew-start`
- [ ] `.claude/skills/crew-start/SKILL.md` + `skills/crew-start/SKILL.md`
      (copie plugin) : après le choix de batch (anti-collision `manager`
      existante, inchangée) — créer le worktree
      `../<repo-name>-batch-<slug>/` sur branche `crew/batch-<slug>` s'il
      n'existe pas, ou le réutiliser si déjà présent pour ce batch
      (reprise / 2e tâche du même batch).
- [ ] `cd` dans le worktree pour le reste du tour ; chemins absolus
      pointant vers la copie worktree des fichiers (pas le checkout
      principal) pour `Read`/`Edit`/`Write`.
- [ ] Enregistrement de la session dans `crew_lock.json` (batch, tasks,
      worktree, branch, timestamp) sous `LocksMutex`.
- [ ] Cas conflit : 2e session tentant `/crew-start` sur un batch dont le
      worktree/lock est déjà tenu par un autre `session_id` → bloquée
      (`exit(2)`) avant toute édition (même règle que `_claim_resume_lock`
      actuel).

### `/crew-close-task`
- [ ] `.claude/skills/crew-close-task/SKILL.md` (+ copie plugin) : rebase
      `crew/batch-<slug>` sur `main` courant.
- [ ] Rebase propre → merge fast-forward, suppression worktree + branche,
      retrait de l'entrée session dans `crew_lock.json`.
- [ ] Conflit au rebase → abort, worktree + branche conservés, fichiers en
      conflit signalés à l'utilisateur ; entrée `crew_lock.json` de la
      session quand même retirée (le travail est fini même si
      l'intégration ne l'est pas).
- [ ] Pas de remote git : rebase local uniquement, pas de `fetch` —
      documenté comme contrainte, pas silencieusement ignoré.

### `/crew-status`
- [ ] `.claude/skills/crew-status/SKILL.md` (+ copie plugin) :
      avertissement pour tout worktree sur disque sans entrée session
      correspondante dans `crew_lock.json` (crash / `/crew-close-task`
      jamais lancé) — signalé pour nettoyage manuel, pas de suppression
      automatique.

### Sync plugin
- [ ] `scripts/crew_hook.py` : resync depuis `crew/crew_hook.py` en toute
      fin de tâche (même procédure que les rounds précédents de
      hardening du batch-lock — commits `dffbcdd`, `7800e48`,
      `5ae46e6`).

### Tests
- [ ] `crew/TESTS/IA/worktree-batch-isolation.md` (non coché) :
  - 🤖 `/crew-start` sur 2 batches à zones non chevauchantes depuis 2
    sessions simulées → 2 worktrees créés, chaque session n'écrit que
    dans le sien (zéro fichier partagé écrit hors worktree).
  - 🤖 `/crew-close-task` avec rebase propre → merge fast-forward,
    worktree + branche supprimés, entrée `crew_lock.json` vidée.
  - 🤖 `/crew-close-task` avec conflit sur `main` → merge abort, worktree
    + branche survivent, conflit signalé, entrée `crew_lock.json` quand
    même vidée.
  - 🤖 Gate renforcé : appel `Edit` sur un chemin sous une `Zone:`
    verrouillée par une autre session → bloqué (`exit(2)`) ; même chemin
    sans verrou actif ou verrouillé par la session appelante → autorisé.
  - 🤖 Purge TTL : entrée session > 6h supprimée au `Stop` suivant ;
    `/crew-status` signale le worktree désormais orphelin.
  - 🤖 Collision de reprise : 2e session tentant `/crew-start` sur un
    batch déjà réclamé (worktree + lock tenus par un autre `session_id`)
    bloquée avant toute édition.
- [ ] `crew/TESTS/DEV/worktree-batch-isolation.md` (non coché) :
  - 🖱️ Run manuel 2 terminaux : ouvrir 2 vraies sessions Claude Code,
    `/crew-start` sur 2 batches différents en simultané, confirmer zéro
    contamination croisée et un merge propre pour les deux à la clôture.

### Clôture
- [ ] Historiser dans `crew/CLAUDE_CONTEXT/HISTORIQUE.md`.
- [ ] Sortir les tests ci-dessus dans `crew/TESTS/IA/` et
      `crew/TESTS/DEV/` (créés non cochés dès cette tâche — cf. section
      Tests — ne pas cocher avant validation réelle).

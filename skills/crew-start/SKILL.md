---
name: crew-start
description: Reprend le travail crew sans préciser quoi — continue la tâche en CURRENT_TASKS, sinon démarre un batch inactif depuis TODO (anti-collision), puis code. Trigger — "/crew-start", "continue le travail", "lance la suite".
---

Point d'entrée unique pour reprendre une session crew sans avoir à dire
quelle tâche. Le **choix** de la tâche est fait par un script déterministe
(`crew_hook.py next-task`) ; ce skill déroule ensuite le démarrage
(verrou, worktree, `git mv`), l'implémentation, puis `/crew-close-task`.

**Ancrage racine obligatoire** : tout chemin `crew/...` se résout depuis la
racine du repo (`git rev-parse --show-toplevel`), jamais depuis le cwd
courant (sinon un `crew/` fantôme est créé dans un sous-dossier). Le
`git worktree add`/`cd` des étapes 3-4 s'exécute depuis la racine du
checkout principal.

## Étapes

1. **Choisir la tâche** (lecture seule, ~0 token de raisonnement) :

   ```bash
   ROOT="$(git rev-parse --show-toplevel)"
   HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
   CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" next-task
   ```

   (plugin : `scripts/crew_hook.py` du plugin ; clone manuel :
   `crew/crew_hook.py`). Sortie JSON : `action`, `task`, `batch`,
   `worktree`, `branch`, `skipped[{slug,reason}]`, `paused`,
   `unclassified`, `ambiguous`. Il couvre déjà : verrous des autres sessions,
   batchs actifs/en pause, chevauchement de `Zone :`, ICEBOX et « À classer »
   ignorés. Ne pas refaire ce tri à la main.

   Si `paused` n'est pas vide, le signaler à l'utilisateur (tâche + ce qui
   bloque) — une tâche de `PAUSED/` n'est JAMAIS reprise automatiquement.

2. **Selon `action`** :
   - `resume` → étape 3 (Cas reprise). Si `ambiguous` : demander à
     l'utilisateur laquelle prioriser plutôt que deviner.
   - `start` → étape 3 (Cas démarrage).
   - `classify` → des tâches de `TODO/` n'ont ni batch ni zone
     (`unclassified`) : dispatcher `Agent({subagent_type: "manager"})` pour
     les classer (zone d'impact + batch, cf. `CLAUDE.md` § Batching), puis
     relancer l'étape 1.
   - `none` → rien de démarrable : dire pourquoi à l'utilisateur à partir de
     `skipped` (verrou, batch actif, chevauchement) ou « TODO vide », et
     s'arrêter. Seul cas où le skill s'arrête sans avoir codé.

3. **Verrou + isolation** (à faire avant toute édition) :
   - *Reprise* : exécuter `Bash({command: ': "crew-resume:<task>"'})` (no-op
     qui pose le verrou via le hook `PreToolUse`).
   - Créer ou réutiliser le worktree du batch :
     `git worktree add -b <branch> <worktree> main` (valeurs du JSON ;
     `git worktree list` d'abord : s'il existe déjà, ne pas le recréer, y
     compris sous un ancien slug `…-batch-<slug>-…`). `cd` dedans et
     utiliser des chemins absolus de cette copie pour tout `Read`/`Edit`/
     `Write` suivant.
   - *Démarrage* : depuis le worktree,
     `git mv crew/TODO/<task> crew/CURRENT_TASKS/<task>`, mettre à jour les
     deux `INDEX.md`.

   - *Nommer la session* (démarrage uniquement ; en reprise le hook
     SessionStart l'a déjà fait) : afficher à l'utilisateur
     `/rename <slug de la tâche sans .md>` — un hook ne peut pas renommer une
     session en cours, seul SessionStart le peut.

4. **Le hook bloque (exit 2)** — verrou pris ou batch occupé entre le choix
   et le claim (course entre sessions) : ne pas insister. Relancer l'étape 1
   (le script voit maintenant le verrou et propose la tâche suivante). Ne
   s'arrêter que sur `action: none`.

5. **Implémenter** : relire le fichier de la tâche, traiter les actions
   `- [ ]` dans l'ordre, avec les skills du routage de `CLAUDE.md`
   (`test-driven-development`, `systematic-debugging`, `graphify`…). Cocher
   chaque action quand elle est réellement finie (pas en avance, pas en lot).

6. Toutes les actions cochées → enchaîner directement sur `crew-close-task`
   (sans demander confirmation, elle fait partie du protocole).

## Ce que ce skill ne fait pas

- Ne démarre jamais deux tâches de batchs différents dans la même
  invocation — un `/crew-start` = une tâche jusqu'à sa clôture (ou
  blocage réel).
- Ne pioche jamais dans `crew/ICEBOX/` ni dans « À classer » sans
  classification par `manager`.
- Ne reprend jamais automatiquement une tâche de `crew/PAUSED/`.
- Ne coche pas d'actions non terminées, ne saute pas le verrou/anti-collision.
- Ne remplace pas `/crew-close-task` — l'appelle en fin de tâche.

# Historique des tâches terminées

Une entrée par tâche finie (code terminé) : quoi, quand, fichiers/commits
clés. Mémoire de contexte du projet — ne pas résumer, garder les détails qui
aideraient une session future à comprendre pourquoi une décision a été prise.

## worktree-batch-isolation — 2026-08-22
Quoi : implémente la spec `docs/superpowers/specs/2026-08-22-worktree-batch-
isolation-design.md` — remplace le verrouillage batch coopératif/rétroactif
par une isolation à deux couches : Layer 1 (garantie physique) = chaque
batch actif tourne dans son propre `git worktree` (`../<repo>-batch-<slug>/`
sur branche `crew/batch-<slug>`, nommage déterministe via `_batch_slug`/
`_worktree_paths_for`) ; Layer 2 (filet de sécurité) = gate `PreToolUse`
durci de `Bash` seul à `Bash|Edit|Write|MultiEdit`, bloquant toute écriture
(`Edit`/`Write`/`MultiEdit`) ou commande mutante (`rm`/`mv`/`cp`/
redirection) touchant un chemin sous une `Zone:` verrouillée par une AUTRE
session.
- `crew/crew_hook.py` (+ copie plugin `scripts/crew_hook.py`, resync exact
  sauf la divergence pré-existante `ROOT`/`CLAUDE_PROJECT_DIR`) : nouveau
  schéma `crew_lock.json` (remplace `.batch_locks.json`) session→`{batch,
  tasks, worktree, branch, since}` au lieu d'une map plate slug→session ;
  `check_batch_collisions`/`check_zone_overlaps`/`_section_lock_sessions`/
  `regen_batch_locks_md` dérivent désormais slug→session via
  `_slug_session_map` ; nouveau `gate_pretooluse` avec `_gate_check_path`/
  `_locked_zones_by_others`/`_path_locked_by_other`/`_extract_candidate_paths`.
- **Bug critique trouvé en code review et corrigé avant clôture** : la
  comparaison chemin-vs-zone comparait un `file_path` ABSOLU (toujours
  fourni par `Edit`/`Write`/`MultiEdit`) à une `Zone:` relative sans
  normalisation — le gate durci ne bloquait donc JAMAIS rien en pratique
  (fail-open silencieux à 100%). Corrigé via `_repo_relative_path` (résout
  `path` relatif à `ROOT` ou à la racine d'un worktree de batch connu) +
  `_path_matches_zone` (ajoute le support `fnmatch` pour les `Zone:` à glob,
  ex. `.claude/skills/crew-*` utilisé par ce dépôt lui-même — l'ancien
  `_expand_brace_glob` ne gérait que `{a,b,c}`, pas `*`). Vérifié en live
  (chemin absolu réel du dépôt + chemin sous un worktree simulé).
- `.claude/skills/crew-start/SKILL.md`, `crew-close-task/SKILL.md`,
  `crew-status/SKILL.md` (+ copies plugin `skills/`) : procédures de
  création/réutilisation de worktree, rebase+merge+teardown à la clôture
  (abort proprement sur conflit, jamais de résolution auto), détection de
  worktree orphelin.
- `hooks/hooks.json` (matcher élargi en place) + `.claude/settings.json`
  (nouveau bloc `Edit|Write|MultiEdit` séparé du bloc `Bash` existant, pour
  ne pas mélanger avec le hook graphify non lié).
- `.gitignore`/`template/.gitignore` : `.batch_locks.json`/`.batch_locks.mutex`
  → `crew_lock.json`/`.crew_lock.mutex`. Stale `.batch_locks.json` supprimé.
- Tests sortis (non cochés) : `crew/TESTS/IA/worktree-batch-isolation.md`
  (9 items 🤖/🔍, dont le test du gate explicitement renforcé pour exiger un
  chemin ABSOLU suite au bug ci-dessus) et `crew/TESTS/DEV/
  worktree-batch-isolation.md` (1 item 🖱️, run manuel 2 terminaux).
- Passe `simplify` post-review : helper `_tokenize_command` partagé entre
  `_extract_git_mv_task`/`_extract_candidate_paths` (dédup) ; `locks`/
  `sections` chargés une fois et propagés dans `gate_pretooluse`/
  `_gate_check_path`/`check_zone_overlaps` au lieu d'être relus par chemin
  candidat ; `_register_task_lock` : un seul chemin de dérivation batch/
  worktree/branch (au lieu de deux variantes dupliquées) + avertissement
  stderr si une session enregistre une tâche d'un batch différent de celui
  déjà détenu (incohérence, ne devrait jamais arriver). Piste de fond non
  appliquée (hors scope, changerait l'interface) : exposer `_batch_slug`/
  `_worktree_paths_for` via un mode CLI de `crew_hook.py` pour que les
  SKILL.md l'appellent au lieu de re-dériver l'algorithme en prose —
  actuellement dupliqué (Python + prose), risque de dérive silencieuse si
  l'algo Python change sans mettre à jour les 3 skills × 2 copies.

## marketplace-plugin — 2026-08-22 (clôture)
Quoi : clôture tardive de la tâche `marketplace-plugin.md` — le code était
déjà fait depuis le 2026-08-20 (repackaging claude-crew en plugin Claude
Code marketplace : `template/`, `skills/`, `agents/`, `scripts/`,
`hooks/hooks.json`, `.claude-plugin/{plugin,marketplace}.json`, `crew-init`
réécrit pour lire `${CLAUDE_PLUGIN_ROOT}/template/`), mais jamais fermée
côté crew (cases jamais cochées, rien dans `HISTORIQUE.md`, tests jamais
sortis) — découvert en voulant démarrer une tâche voisine du même batch
(`worktree-batch-isolation.md`) qui touche les mêmes fichiers
(`crew_hook.py`, `scripts/`, `.claude/skills/crew-*`) et devait être
séquencée après. Vérification rétroactive de chaque item avant de cocher
(pas de coche à l'aveugle) :
- Trouvé + corrigé au passage : `skills/crew-new-task/SKILL.md` (racine
  plugin + copie locale `.claude/skills/crew-new-task/SKILL.md`)
  conditionnait le dispatch de la persona `manager` sur l'existence du
  fichier local `.claude/agents/manager.md` — référence obsolète depuis que
  le plugin fournit `agents/manager.md` directement. Reformulé pour couvrir
  les deux sources (plugin ou local).
- Item "diff `template/` vs export frais `~/.claude/templates/
  project-scaffold/` → aucune dérive" : dérive massive constatée en
  re-testant maintenant, mais lu comme une vérification ponctuelle à la
  copie initiale (2026-08-20), pas un invariant permanent — la spec
  (`docs/superpowers/specs/2026-08-20-marketplace-plugin-design.md`,
  § "What moves where") documente explicitement que le repo devient source
  de vérité et que la copie locale est censée devenir obsolète après coup.
- Tests sortis : `crew/TESTS/IA/marketplace-plugin.md` (4 items 🤖/🔍, à
  re-dérouler une session future) et `crew/TESTS/DEV/marketplace-plugin.md`
  (3 items 🖱️, end-to-end marketplace install depuis un profil propre).

## batch-lock-hardening-quick-wins — 2026-08-22
Quoi : suite à une remarque utilisateur listant 6 failles du verrouillage
batch multi-session (blocage rétroactif pas préventif, `.batch_locks.json`
sans verrou OS, `check_zone_overlaps` non bloquant, tâche non catégorisée
sans protection, dépendance à un hook Stop coopératif, pas de rollback),
persona `architect` dispatchée pour brainstormer/prioriser. Verdict : la
faiblesse "dépend du hook actif dans les deux sessions" n'a pas de correctif
applicatif (plafond structurel — la vraie réponse reste `git worktree` par
session, déjà recommandée dans CLAUDE.md § Batching) ; rollback
transactionnel écarté (sur-ingénierie pour un usage solo-dev). 3 quick wins
implémentés :
1. `LocksMutex` (O_CREAT|O_EXCL sur `.batch_locks.mutex`, portable Windows —
   pas de fcntl) autour de la section read-modify-write de
   `.batch_locks.json`, + écriture atomique (`os.replace`) dans `save_locks`.
2. Garde `PreToolUse` (matcher `Bash`) : `gate_pretooluse` bloque *avant*
   exécution un `git mv crew/TODO/x.md crew/CURRENT_TASKS/x.md` si la tâche
   n'est catégorisée dans aucun batch de `CLAUDE_BATCH.md`, ou si une
   voisine de son batch est déjà verrouillée par une autre session — en
   complément (pas remplacement) du contrôle `Stop` rétroactif existant.
3. `check_zone_overlaps` devient bloquant, mais uniquement quand les deux
   batchs en collision sont verrouillés par des `session_id` différents
   (même filtre que `check_batch_collisions`) — pour ne pas bloquer une
   session solo qui travaille séquentiellement sur deux batchs à zones
   voisines.
Fichiers/commits clés :
- `crew/crew_hook.py` (source) + `scripts/crew_hook.py` (copie
  plugin-packagée, resynchronisée à l'identique sauf les 2 lignes
  intentionnellement divergentes : import + résolution `ROOT` via
  `CLAUDE_PROJECT_DIR`) : `LocksMutex`, `save_locks` atomique,
  `_extract_git_mv_task`/`gate_pretooluse`, `check_zone_overlaps` (retourne
  désormais `(warnings, blocking)`), `load_sections()` (helper factorisé,
  utilisé par `main()` et `gate_pretooluse`).
- `.claude/settings.json` + `hooks/hooks.json` : nouvelle entrée
  `PreToolUse`/`Bash` appelant `crew_hook.py`.
- Revue : `requesting-code-review` (medium) a trouvé 2 bugs réels, corrigés
  avant clôture — (a) `LocksMutex.__exit__` retirait le marqueur même quand
  `__enter__` n'avait pas réussi à l'acquérir (timeout/erreur), risquant
  d'effacer le verrou d'une AUTRE session encore en écriture ; (b)
  `_extract_git_mv_task` ne regardait que la première occurrence de `mv`
  dans la commande, ratant un `git mv` réel situé après un `mv` sans
  rapport dans une commande composée (`a; b && git mv ...`).
- `simplify` (4 angles en parallèle) : reuse propre (aucun fix). 4 fixes
  simplification (hissé le calcul de `sessions_a` hors de la boucle
  imbriquée dans `check_zone_overlaps` ; pré-init morte
  `zone_warnings, zone_blocking = [], []` supprimée ; duplication du
  chargement de `sections` factorisée dans `load_sections()` ; `import
  shlex` remonté en haut de fichier au lieu d'un try/except autour de
  l'import). 1 fix efficiency (sortie de `check_zone_overlaps` du bloc `with
  LocksMutex():` — calcul pur, pas de raison de retenir le mutex plus
  longtemps, réduit la contention pour d'autres sessions). 1 skip efficiency
  (fusionner le hook `PreToolUse` graphify existant avec la nouvelle garde
  batch dans un seul process : hors scope, coupplerait deux préoccupations
  non liées pour un gain marginal — deux process Bash occasionnels, pas une
  hot loop). 1 fix altitude, bug réel trouvé : `shlex.split(command,
  posix=(sys.platform != "win32"))` liait le dialecte shell parsé à l'OS
  hôte au lieu du fait que le tool Bash exécute toujours du POSIX (Git
  Bash) — sur Windows ça cassait silencieusement le slug extrait d'un
  chemin entre guillemets (guillemets restaient dans le token, échec du
  test `.endswith(".md")`, la garde ne se déclenchait jamais). Fixé en
  `posix=True` figé. Autre fix altitude mineur : `"TODO/"`/`"CURRENT_TASKS/"`
  en dur remplacés par `DIRS["TODO"].name`/`DIRS["CURRENT_TASKS"].name`
  (source unique déjà existante).
- Vérification : suite de smoke tests dédiée
  (`test_crew_hook_locks.py`, scratchpad — appelle les fonctions pures sans
  toucher au vrai `crew/TODO`/`CURRENT_TASKS`) + invocations réelles
  end-to-end (`echo '{...}' | python crew/crew_hook.py`) confirmant le
  blocage `exit(2)` sur une tâche non catégorisée et le passage silencieux
  `exit(0)` sur une commande Bash quelconque, + `Stop` toujours propre +
  `scripts/dev/verify_plugin_package.py` PASS (7 checks) après resync.

<!-- Exemple :
## <slug de la tâche> — AAAA-MM-JJ
Quoi : ...
Fichiers/commits clés : ...
-->

## rename-organized-to-crew — 2026-08-17
Quoi : rename complet du système de suivi de tâches `organized` → `crew`
(nom produit affiché : `claude-crew`). Périmètre confirmé avec l'utilisateur :
ce repo + le template global `~/.claude/templates/project-scaffold/`, GitHub
distant non touché pour l'instant (rename local seulement).
Fichiers/commits clés :
- Dossier `organized/` → `crew/` dans ce repo ; `organized_hook.py` →
  `crew_hook.py` (constante Python `ORGANIZED` → `CREW`) ;
  `spec_to_task_hook.py` mis à jour ; `.claude/settings.json` (commandes de
  hooks + patterns de matcher `*organized*` → `*crew*`, `skip=(...,'organized/',...)`
  → `'crew/'`).
- Skills `.claude/skills/organized-{init,new-task,close-task,status,start}`
  renommés en `crew-{init,new-task,close-task,status,start}` (dossiers +
  `name:`/`description`/trigger dans chaque `SKILL.md`).
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `check_placeholders.py`,
  `.gitignore`, `.claude/agents/{ceo,manager,architect,comms}.md` mis à jour.
  Note : `README.md` garde intentionnellement les URLs GitHub existantes
  (`github.com/Nakken13/organized`) puisque le remote n'est pas renommé.
- Même rename propagé au template global
  `~/.claude/templates/project-scaffold/` : dossier `ORGA/` → `crew/`,
  `orga_hook.py` → `crew_hook.py` (constante `ORGA` → `CREW`), skills
  `orga-*` → `crew-*`, docs (`CLAUDE.md`, `README.md`, `AGENTS.md`,
  `CONTRIBUTING.md`, `.claude/settings.json`, `.claude/agents/*.md`).
- Grep exhaustif final (`organized|orga_hook|ORGA|orga-`) sur les deux
  arbres : seuls restent les mentions historiques attendues (fichier de
  tâche lui-même, entrées de changelog/index référençant l'ancien nom, URLs
  GitHub conservées).
- Revue : `requesting-code-review` (verdict "with fixes" — seul point relevé
  était la clôture de tâche elle-même, traitée par cette entrée) et
  `simplify` (4 angles : reuse/simplification/efficiency/altitude — aucun
  fix nécessaire, rename mécanique propre).

## readme-github-discoverability — 2026-08-17
Quoi : suite au rename public `organized` → `claude-crew` et à une revue
`comms` sur la découvrabilité GitHub, correction des URLs cassées et
amélioration du copy pour maximiser le taux de star sur le repo public
`Nakken13/claude-crew`. Volet GitHub UI (topics, description du repo, social
preview image) laissé hors scope — reste à faire manuellement dans les
Settings GitHub.
Fichiers/commits clés :
- `README.md` : URLs `Nakken13/organized` → `Nakken13/claude-crew` (badge +
  commande `git clone`) ; badge GitHub stars retiré du haut (peu de stars =
  contre-productif visuellement) et redéplacé en bas près du CTA existant ;
  nouveau CTA court "star ce repo" ajouté juste après le hook d'ouverture
  `## 🧩 The problem`, en plus de celui déjà en fin de fichier.
- `CONTRIBUTING.md` : template NOM_PROJET/placeholders non remplis
  entièrement réécrit avec les conventions réelles du repo solo-maintenu
  (pas de convention de branche imposée, Conventional Commits préférés mais
  pas obligatoires, PR contre `main`, pas de gate CI).
- Revue : `requesting-code-review` (verdict "Ready to merge: Yes", aucun
  Critical/Important — un point Minor sur la formulation de
  `CONTRIBUTING.md` appliqué directement) et `simplify` (4 angles en
  parallèle : reuse/simplification/efficiency/altitude — aucun fix
  nécessaire, diff markdown propre et scopé).

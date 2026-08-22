# Historique des tâches terminées

Une entrée par tâche finie (code terminé) : quoi, quand, fichiers/commits
clés. Mémoire de contexte du projet — ne pas résumer, garder les détails qui
aideraient une session future à comprendre pourquoi une décision a été prise.

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

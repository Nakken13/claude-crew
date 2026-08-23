# Historique des tâches terminées

Une entrée par tâche finie (code terminé) : quoi, quand, fichiers/commits
clés. Mémoire de contexte du projet — ne pas résumer, garder les détails qui
aideraient une session future à comprendre pourquoi une décision a été prise.

## mecanisme-mise-a-jour-scaffold-multi-projets — 2026-08-23
Quoi : mécanisme de mise à jour (`/crew-update`) pour un projet déjà
bootstrapé via `crew-init`, récupérant les évolutions ultérieures des
fichiers "moteur" du scaffold sans jamais toucher aux données utilisateur
(`crew/TODO/`, `CURRENT_TASKS/`, `PROBLEMS/`, `ICEBOX/`, `TESTS/`,
`HISTORIQUE.md`) ni écraser silencieusement un fichier personnalisé.
Moteur `crew/crew_update.py` (+ `scripts/crew_update.py` resync) :
`classify(local_hash, recorded_hash, source_hash)` — fonction pure à 5
statuts (`absent`/`new`/`removed`/`up_to_date`/`apply`/`conflict`), le hash
de la dernière écriture connue étant stocké dans
`crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json` (écriture atomique temp+`os.replace`,
même idiome que `crew_hook.save_locks()`) plutôt qu'un diff git contre
l'historique du scaffold — décision `architect` : un projet cible n'est pas
un clone du repo scaffold, un hash évite toute dépendance réseau/git.
`plan()`/`apply()`/`record_version()`/`seed()`/`detect_mode()` autour de
cette fonction. Liste blanche scindée `ENGINE_FILES_COMMON` (tout projet)
vs `ENGINE_FILES_LEGACY` (skills/agents/hooks copiés localement — projets
Option C / pré-plugin uniquement ; les projets plugin s'appuient sur
`/plugin update claude-crew` pour ces fichiers-là), sélection auto-détectée
via `detect_mode()` (présence de `.claude/skills/crew-init/SKILL.md`
localement) plutôt que laissée à la seule prose du skill.
Skill dédié `skills/crew-update/SKILL.md` (+ copie `.claude/skills/crew-update/`)
plutôt qu'extension de `crew-init` (romprait sa garantie documentée "ne
réécrit jamais un fichier déjà rempli sans demande explicite"). Confirmation
`AskUserQuestion` obligatoire avant tout `apply()`, jamais d'application
silencieuse.
Déviation vs tâche initiale : pas de nouveau fichier `VERSION` racine — le
champ `version` de `.claude-plugin/plugin.json` (déjà existant, `"0.1.1"`)
sert de source de vérité unique, documenté dans `CONTRIBUTING.md` §
"Versioning the scaffold" avec la convention de bump (patch/minor/major) et
`CHANGELOG.md` (nouveau, entrée rétroactive 0.1.1 + `[Unreleased]`).
Découverte au passage (non corrigée, hors scope) : `.claude/skills/crew-init/SKILL.md`
a dérivé de `skills/crew-init/SKILL.md` (décrit encore l'ancien flux Option C
copiant skills/agents/hooks, alors que la version plugin à jour ne copie
plus que CLAUDE.md/AGENTS.md/PRODUCT.md/CONTRIBUTING.md/SECURITY.md/
check_placeholders.py/crew/) — filée dans `crew/PROBLEMS/derive-crew-init-skill-init-vs-claude-skills.md`.
- **2 problèmes trouvés en code review et corrigés avant clôture** :
  (1) `classify()` renvoyait `apply` pour un fichier disparu de la source
  (déplacé/supprimé en amont — ex. exactement ce qui est arrivé à
  `crew_hook.py` lors du repackaging plugin), et `apply()` plantait ensuite
  (`FileNotFoundError` sur `shutil.copyfile`) — reproduit en live par le
  reviewer. Corrigé par un 5e statut `removed` (jamais appliqué
  automatiquement, signalé pour décision manuelle). (2) gap pratique majeur :
  sans `SCAFFOLD_VERSION.json` existant (tous les projets bootstrapés avant
  ce mécanisme), le premier `/crew-update` classait *tout* fichier divergent
  en `conflict` (aucun hash enregistré pour prouver l'absence de
  personnalisation) et n'appliquait donc jamais rien automatiquement —
  exactement le cas d'usage visé par la tâche. Corrigé par `seed()`
  (`--seed`/`--source-version`, refuse par construction d'écraser un
  historique déjà enregistré sauf `force=True`) qui accepte le contenu local
  actuel comme baseline de confiance explicite.
- Passe `simplify` (4 agents parallèles reuse/simplification/efficacité/
  altitude) : écriture atomique reprise de `crew_hook.save_locks()` (au lieu
  d'un `write_text` nu — `SCAFFOLD_VERSION.json` est relu à chaque run
  suivant, une troncature en cas de crash casserait la détection de
  personnalisation) ; dédoublonnage de 7 occurrences du pattern
  `{rel: hash_file(...) for rel in WHITELIST}` + `save_scaffold_version` dans
  les tests, remplacées par `seed()` ; `seed()` durci contre l'écrasement
  silencieux d'un historique existant (`force=` explicite requis) ; détection
  legacy/plugin extraite de la prose du skill vers `detect_mode()` (testable,
  seule source de vérité, `--legacy` reste un override CLI). Angle
  efficacité : rien d'actionnable (CLI manuelle, échelle de quelques
  fichiers).
- Tests : `crew/test_crew_update.py` créé (aucun n'existait), 23 tests
  pytest (TDD strict : RED confirmé avant chaque implémentation/correctif,
  y compris les 2 bugs de review et les 2 durcissements de la passe
  simplify), fixtures `tmp_path` avec fichiers réels, aucun mock. Suite
  complète `crew/` = 31 passed (`python -m pytest crew/ -q`).
- Fichiers clés : `crew/crew_update.py`, `scripts/crew_update.py`,
  `crew/test_crew_update.py`, `skills/crew-update/SKILL.md`,
  `.claude/skills/crew-update/SKILL.md`, `skills/crew-init/SKILL.md`
  (pointeur `/crew-update`), `CONTRIBUTING.md`, `README.md`, `CHANGELOG.md`,
  `crew/PROBLEMS/derive-crew-init-skill-init-vs-claude-skills.md`.

## hook-auto-commit-cloture-tache — 2026-08-22
Quoi : `auto_commit_closure(finished, now_dt)` + helper `_closure_commit_scope`
dans `crew/crew_hook.py` (+ `scripts/crew_hook.py` resync) — commit git
**local uniquement** (jamais de push) scopé à `crew/`, déclenché par slug
réellement clôturé : un slug de `finished` n'est retenu que s'il a une
entrée correspondante dans le diff (non commit) de `HISTORIQUE.md` — pas
juste « le fichier a bougé quelque part » (couvre 2 tâches finies le même
tour dont une seule vraiment historisée). Scope explicite (`git add --
<chemins>`, jamais `-A`/`.`) ; commit lui-même scopé au pathspec (`git
commit -- <chemins>`) plutôt qu'un `git commit` nu, pour ne jamais embarquer
un changement déjà stagé par l'utilisateur ailleurs dans le dépôt — exactement
l'incident (ProjetA, config backend committée/poussée sans revue par une
session jamais formellement close) qui motive cette tâche. Idempotence via
`git diff --cached --quiet` restreint au scope calculé (pas de flag manuel).
Échec (hook `pre-commit` qui rejette, chemin invalide, etc.) capturé et
loggé sur stderr, jamais levé — même contrat que le reste du hook.
- **2 bugs critiques trouvés en code review et corrigés avant clôture** :
  (1) `crew/CLAUDE_CONTEXT/BATCH_LOCKS.md` est gitignoré et jamais suivi
  mais régénéré sur disque à chaque tour — un `git add` explicite dessus
  était refusé par git et faisait échouer TOUT le `git add` en une seule
  commande, donc **aucun commit n'était jamais créé** dans le vrai dépôt
  (silencieux, avalé par le `except Exception`). Corrigé en filtrant les
  candidats via `git check-ignore` (`_git_ignored`), pas seulement
  suivi-ou-absent. (2) `git commit -m msg` (sans pathspec) commite l'index
  ENTIER, pas seulement ce qui vient d'être `git add`é — un fichier de
  l'utilisateur déjà stagé ailleurs (hors `crew/`) au moment du hook aurait
  été embarqué dans le commit de clôture, reproduisant exactement l'incident
  ProjetA que la tâche visait à corriger. Corrigé via `git commit -- <chemins>`
  (commit partiel scopé au pathspec, forme standard git). Les deux bugs ont
  été reproduits en live par le reviewer avant correction, puis couverts par
  2 nouveaux tests de régression.
- Tests : `crew/test_crew_hook.py` créé (aucun n'existait), 8 tests pytest
  (TDD : 5 initiaux avec RED confirmé sur `AttributeError` avant
  implémentation, puis 3 ajoutés en régression post-review — gitignore
  `BATCH_LOCKS.md`, fichier utilisateur déjà stagé non balayé, détection
  par slug plutôt que globale). Dépôt git temporaire isolé par test
  (`tmp_path` + monkeypatch des constantes module `crew_hook`), aucun mock
  sur git/subprocess.
- `crew/CLAUDE_CONTEXT/AGENTS.md` : nouvelle section documentant le
  comportement (commit auto local à la clôture, jamais de push).
- `.claude/settings.json` : vérifié inchangé, l'event Stop existant suffit.
- Travaillé depuis le worktree `../claude-crew-batch-plugin-packaging`
  (branche `crew/batch-plugin-packaging`), rebasé + fast-forward mergé dans
  `main` à la clôture (worktree seule tâche active de ce batch — teardown
  normal, le batch garde des tâches TODO non commencées).
- **Gap découvert en dogfooding le flux worktree** (`/crew-start` Cas B
  depuis un worktree fraîchement créé) : le `git mv` fait depuis le worktree
  n'est jamais vu par la détection `started`/`finished` du hook Stop (elle
  lit toujours `crew/TODO`/`crew/CURRENT_TASKS` du checkout PRINCIPAL, `ROOT`
  étant résolu depuis `__file__` de `crew_hook.py` — toujours le checkout
  principal, jamais le worktree) — donc `_register_task_lock` n'était jamais
  déclenché automatiquement pour ce cas ; contourné manuellement via le
  marqueur `crew-resume:` pour cette session. Tracké dans
  `crew/TODO/fix-worktree-gitmv-lock-registration-gap.md` (même batch,
  position 5), pas corrigé dans cette tâche (hors scope).

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

## fix-worktree-gitmv-lock-registration-gap — 2026-08-23
Quoi : bug de dogfooding découvert sur `worktree-batch-isolation` — `git mv
crew/TODO/<slug>.md crew/CURRENT_TASKS/<slug>.md` lancé depuis un worktree de
batch n'enregistrait jamais le verrou live dans `crew_lock.json` avant le
`Stop` suivant (le hook Stop est ROOT-anchored, il ne voit jamais un
déplacement fait dans `../<repo>-batch-<slug>/`), laissant une fenêtre où une
2e session pouvait démarrer une tâche voisine sans détection. Fix : la
`git mv` branche de `gate_pretooluse` enregistre désormais le verrou de façon
préventive (avant l'exécution réelle du `mv`), sous mutex, avec relecture
fraîche (`load_locks`+`purge_stale_locks`+re-vérification) pour fermer le
TOCTOU avec la lecture `locks` déjà faite plus haut dans la même invocation,
et régénère `BATCH_LOCKS.md` dans la foulée. La boucle `started` du Stop hook
est conservée en fallback documenté (git mv hors du tool Bash suivi, ou
PreToolUse bypassé).
Fichiers/commits clés :
- `crew/crew_hook.py` (+ copie `scripts/crew_hook.py` resynchronisée) :
  nouvelle primitive `_claim_lock` (extraite en `simplify`, partagée par
  `_claim_resume_lock` et la nouvelle `_claim_git_mv_lock`), branche `git mv`
  de `gate_pretooluse` mise à jour, commentaire de justification ajouté sur
  la boucle `started` de `main()`.
- `crew/test_crew_hook.py` : fixture `repo` étendue (monkeypatch
  `LOCKS_FILE`/`LOCKS_MUTEX`, gap de test-isolation corrigé au passage) + 5
  scénarios `test_gate_pretooluse_git_mv_*` (registration immédiate, regen
  `BATCH_LOCKS.md` immédiate, blocage même-slug, blocage TOCTOU, idempotence
  avec le fallback Stop). 13/13 tests passent.
- Revue : `requesting-code-review` (verdict "With fixes" — un point Important
  sur un timestamp `since` figé dans une fixture de test qui aurait fini par
  dépasser le TTL de 6h et casser 2 tests en continu ; corrigé en le
  dérivant de l'heure réelle) et `simplify` (4 angles en parallèle — reuse et
  altitude ont tous deux signalé la duplication `_claim_resume_lock`/
  `_claim_git_mv_lock`, extraite en `_claim_lock` ; efficiency a fait
  remonter `active_task_slugs()` hors du mutex).
- Travaillé depuis le worktree de batch `../claude-crew-batch-plugin-packaging`
  (branche `crew/batch-plugin-packaging`) — dernière tâche de ce batch, qui
  est désormais entièrement clos.

## verif-fork-throwaway
Quoi : tache jetable de validation du commit auto de cloture (test IA). Rien de fonctionnel, supprimee juste apres.

## graphify

Ce projet a (ou aura, via `graphify init`) un graphe de connaissance dans
`graphify-out/` avec god nodes, structure de communautés et relations
cross-fichiers.

Rules:
- Pour les questions sur le code, lancer d'abord `graphify query "<question>"` dès que `graphify-out/graph.json` existe. `graphify path "<A>" "<B>"` pour les relations, `graphify explain "<concept>"` pour un concept ciblé. Sous-graphe scopé, bien plus petit que GRAPH_REPORT.md ou un grep brut.
- Si `graphify-out/wiki/index.md` existe, s'en servir pour la navigation large plutôt que du browsing de source brut.
- **Ne jamais lire `graphify-out/graph.json` ou `graphify-out/GRAPH_REPORT.md` en entier** — uniquement pour une revue d'architecture large quand `query`/`path`/`explain` n'apportent pas assez de contexte.
- Après modification de code, lancer `graphify update .` pour garder le graphe à jour (AST only, pas de coût API).
- Ignorer le bruit de console verbeux (progress bars, percentages) lors des builds ou de `graphify update`.

## Routage des skills

Rules — adapter/retirer les lignes non pertinentes à la stack réelle du projet :
- Question sur l'architecture/le code, exploration avant de lire des fichiers bruts → `graphify` (cf. § graphify ci-dessus ; `/graphify` pour (re)générer le graphe).
- **Nouveau composant/page ou refonte visuelle → `design-taste-frontend` obligatoire** (anti-slop, plugin `taste-skill` ; pré-vol avant tout code visuel) **puis** `frontend-design` (direction esthétique) **puis** `ui-ux-pro-max` pour l'implémentation du composant (adapter à la stack front réelle : Next.js/Tailwind/shadcn, ou autre).
- Audit/retouche d'un écran existant (hiérarchie, a11y, responsive, dark mode, i18n) → `impeccable`.
- **Micro-interaction/animation dans une app React Native (Reanimated/Moti/Lottie)** → `motion-design-rn` (implémentation : choix de lib, timing/easing, perf) **et** `accessibility-motion` (reduced-motion, obligatoire pour CHAQUE animation ajoutée, pas une passe optionnelle en fin de tâche) systématiquement les deux ensemble. Ajouter `haptics` dès qu'un retour tactile est en jeu (press feedback CTA, célébration, erreur) et `sound-design-ui` seulement si un cue sonore est explicitement envisagé (c'est un gate produit — la réponse par défaut est "pas de son", le skill sert à trancher, pas à justifier). Ligne à retirer si le projet n'a pas de stack RN/mobile (cf. § adapter/retirer ci-dessus).
- Ajout d'un chart/graphique (dashboard, analytics) → `dataviz` avant d'écrire le code du chart.
- Bug, test qui échoue, comportement inattendu → `systematic-debugging` avant de proposer un fix.
- Nouvelle feature ou fix → `test-driven-development` : écrire le test avant le code.
- Feature ambiguë ou plusieurs approches possibles → `brainstorming` avant tout code.
- 2+ tâches indépendantes sans état partagé → `dispatching-parallel-agents` pour les paralléliser plutôt que les enchaîner en série.
- Feature work nécessitant une isolation du workspace courant (éviter de polluer une branche en cours) → `using-git-worktrees` avant de démarrer.
- Plan d'implémentation avec tâches indépendantes à exécuter dans la session courante (alternative à `executing-plans` en session séparée) → `subagent-driven-development`.
- Modif touchant l'auth, les tokens, le chiffrement, les secrets, les policies de sécurité → `security-review` avant merge. Le plugin `security-guidance` tourne en continu en complément (pattern-based sur chaque edit + revue LLM au Stop) — les deux se complètent, ne pas désactiver l'un au profit de l'autre.
- **Composant frontend créé ou retouché → il doit être testé responsive** (mobile/tablette/desktop) avant de déclarer le changement terminé — via le MCP `playwright` (viewport scriptés, préféré pour un scénario reproductible) ou `run` + `claude-in-chrome`/`mcp__claude-in-chrome__resize_window` pour une vérification visuelle ponctuelle. Ne pas se contenter d'un typecheck/build qui passe.
- Changement front à valider visuellement → `run` puis `playwright` (scénario scriptable) ou `claude-in-chrome` (golden path + edge cases) avant de déclarer le changement terminé.
- Test navigateur qu'on s'apprête à ranger dans `crew/TESTS/DEV` (🖱️ manuel) → vérifier d'abord s'il est scriptable avec `playwright` ; si oui, il va dans `crew/TESTS/IA` (🤖), pas DEV — le plugin déplace la frontière IA/DEV définie au §4 de la gestion des tâches.
- Fin de tâche/feature → `requesting-code-review`, puis `simplify` sur le code touché avant de committer.
- Retour de code review reçu (commentaires PR, feedback humain ou agent) → `receiving-code-review` avant d'appliquer les changements demandés.
- Implémentation complète, tests passants, prête à intégrer → `finishing-a-development-branch` pour décider merge direct / PR / squash.
- Avant d'affirmer "c'est fait/testé/ça marche" → `verification-before-completion` (lancer réellement la suite de tests concernée).
- Diagnostics de type en continu (Python via `pyright-lsp`, TS/JS via `typescript-lsp`, si le projet a la stack correspondante) tournent en tâche de fond — ne dispensent pas de lancer la suite de tests/le build avant de clore une tâche, ce sont des signaux complémentaires, pas une preuve de correction fonctionnelle.
- Après une session qui modifie durablement `CLAUDE.md`/`AGENTS.md`/les règles crew → `claude-md-management` pour auditer la qualité et capturer les learnings plutôt que de le faire à la main.
- LLM/agent : vérifier quel provider est réellement utilisé (`grep` dans le code, ne pas supposer) avant d'invoquer `claude-api` — ce skill ne s'applique que si le projet appelle réellement l'API Claude/Anthropic.
- Tâche multi-étapes avec un plan à tracker → **`crew/TODO` → `CURRENT_TASKS` → `HISTORIQUE`/`TESTS` reste la source unique de vérité** (cf. § ci-dessous) ; ne pas dupliquer ce tracking avec les skills `writing-plans`/`executing-plans` ni l'outil `TaskCreate` du harness. Utiliser `writing-plans`/`executing-plans` seulement pour une tâche explicitement hors du périmètre crew (ex. session exploratoire sans fichier `crew/*`).

## Personas (subagents `.claude/agents/`) — routage obligatoire

Quatre personas dédiées (`Agent({subagent_type: "<nom>"})`), à ne pas confondre avec les skills ci-dessus — elles portent un point de vue/rôle, pas une procédure technique.

**Si tu penses qu'il y a ne serait-ce que 1% de chance qu'une persona s'applique, tu DOIS la dispatcher. Ce n'est pas négociable — ne pas traiter la question toi-même à sa place.**

- Décision business/priorisation ambiguë, arbitrage scope, "est-ce que ça vaut le coup", choix entre plusieurs directions produit → `ceo` (lecture seule, pas d'implémentation).
- Demande à découper en tâches suivables avant (ou au lieu) de coder, découpage en lots/batches, séquencement → `manager` (écrit/déplace des fichiers `crew/`, applique le cycle de vie et le batching).
- **Démarrage d'une tâche existante** (« fais la tâche X », déplacement `crew/TODO/` → `crew/CURRENT_TASKS/`) → `manager` aussi, systématiquement, pour la vérification anti-collision de fichiers (cf. § Batching) avant de lancer quoi que ce soit — pas seulement au moment du découpage initial.
- Copy marketing/landing/pub/email, ton de marque, wording utilisateur final → `comms` (vérifier `AGENTS.md` avant de toucher au ton d'un agent conversationnel produit s'il en existe un).
- Choix technique structurant (lib/pattern engageant, "on refactore maintenant ou plus tard", arbitrage dette technique) sur du scope déjà défini → `architect` (lecture seule, pas d'implémentation, pas d'arbitrage business).

Signaux d'alerte — si une de ces pensées traverse l'esprit, c'est probablement une rationalisation pour éviter de dispatcher :
- *« Je peux répondre directement, c'est rapide »* → la rapidité ne dispense pas de la persona si le sujet (business/planning/copy) matche.
- *« Ce n'est pas vraiment une décision business/un découpage/de la copy »* → si le doute existe, dispatcher quand même.
- *« Le user a juste posé une question simple »* → une question simple sur la priorisation reste une décision `ceo`.
- *« Je peux trancher ce choix technique moi-même, c'est rapide »* → si 2+ approches raisonnables existent sur un choix structurant, dispatcher `architect` quand même.

Ne pas invoquer ces personas pour de l'implémentation de code — elles cadrent une décision ou un texte, le code reste porté par la session principale ou les skills de la section précédente. En cas de doute réel entre deux personas, choisir la plus proche du cœur de la demande plutôt que de s'abstenir. Les personas de ce scaffold sont génériques (placeholders `<NOM_PROJET>`) : les adapter à la voix de marque et à l'organisation réelles du projet.

## Commandes dédiées crew (`/crew-*`)

Le cycle de vie et le batching ci-dessous sont des **règles documentées** ;
ces skills en sont l'**exécution outillée** — à utiliser plutôt que de
dérouler le protocole à la main à chaque fois :

- `/crew-init` — bootstrap initial du scaffold sur ce projet (copie des
  fichiers, détection stack, résolution des placeholders `<...>`,
  `check_placeholders.py`). À lancer une seule fois, en début de projet.
- `/crew-new-task` — crée une tâche (`TODO/` ou `CURRENT_TASKS/`) en
  respectant le cycle de vie et le batching (§ ci-dessous).
- `/crew-close-task` — clôture une tâche `CURRENT_TASKS/` terminée :
  vérifie les cases cochées, applique les passes obligatoires
  (`requesting-code-review`, `simplify`), historise, sort les tests.
- `/crew-status` — rapport lecture seule : batchs actifs et chevauchements,
  avancement des tâches en cours, tests IA non cochés, tâches TODO
  orphelines.
- `/crew-start` — reprend le travail sans préciser quoi : continue la
  tâche déjà en `CURRENT_TASKS/` s'il y en a une, sinon démarre un batch
  pas encore actif depuis `TODO/` (anti-collision via `manager`), code,
  puis enchaîne `/crew-close-task` en fin de tâche.

## Gestion des tâches — cycle de vie unique (modèle par dossiers)

Chaque tâche = **un fichier `.md`**, qui **se déplace de dossier** selon son état. Un seul fichier la décrit à la fois — ne jamais dupliquer une tâche dans deux dossiers.

```
Problème brut    →  crew/PROBLEMS/<slug>.md
Pas commencée    →  crew/TODO/<slug>.md
Parkée (choix)   →  crew/ICEBOX/<slug>.md   (depuis TODO, dépriorisation explicite ; pour la reprendre, revenir dans TODO d'abord)
Commencée        →  déplacer le fichier vers crew/CURRENT_TASKS/<slug>.md   (mv, plus dans crew/TODO)
Code fini        →  crew/CLAUDE_CONTEXT/HISTORIQUE.md  +  crew/TESTS/<chantier>.md
                    (fichier crew/CURRENT_TASKS supprimé)
Validée (testée) →  cases cochées dans crew/TESTS/<chantier>.md
                    (quand un test de crew/TESTS/IA/ est entièrement validé/coché,
                    le fichier est déplacé vers crew/CLAUDE_CONTEXT/TESTS_DONE/ et supprimé de IA/)
```

Source unique = les dossiers `crew/`. (Un `PROBLEMS.md`/`TODO.md` racine, s'il existe pour compat historique, doit rester un **pointeur** vers `crew/PROBLEMS/` et `crew/TODO/`, jamais une source parallèle.)

`crew/ICEBOX/<slug>.md` — idée/tâche **parkée volontairement**, distincte de `TODO/` (qui veut dire "pas encore commencée mais prévue"). Pas de deadline, pas de batch, n'apparaît pas dans les vérifications `CLAUDE_BATCH.md`. Ne jamais démarrer une tâche directement depuis ICEBOX : la remettre dans `TODO/` d'abord pour qu'elle rentre dans le cycle normal (batching inclus).

### 0. `crew/PROBLEMS/<slug>.md` — inbox des problèmes
- Un fichier par bug / friction / amélioration constaté. Statut `🔴 ouvert` / `🟡 en cours` / `✅ résolu`.
- Quand un problème devient un chantier planifié → en faire une tâche dans `crew/TODO/` (ou directement `crew/CURRENT_TASKS/` si on le démarre).

### 1. `crew/TODO/<slug>.md` — tâches pas commencées
- Le backlog. **Uniquement des tâches jamais commencées** (0 % de code).
- Une tâche = un fichier (description + actions en cases `- [ ]`). `INDEX.md` liste l'ensemble.
- **À l'ajout, catégoriser la tâche dans `crew/CLAUDE_BATCH.md`** (cf. § Batching) : soit dans la zone « À classer », soit directement dans un batch si sa zone d'impact est connue.

### 2. Démarrer une tâche → la **déplacer** vers `crew/CURRENT_TASKS/`
- **Avant tout déplacement, vérification anti-collision obligatoire** (dispatcher `manager`, cf. § Personas) : la zone de fichiers de la tâche à démarrer ne doit chevaucher celle d'**aucun batch actif différent** (batch ayant déjà ≥1 tâche en `crew/CURRENT_TASKS/`). Voir § Batching pour la procédure et le garde-fou automatisé. Chevauchement détecté → ne pas démarrer, séquencer dans le même batch ou attendre.
- **Dès qu'on commence une tâche, déplacer son fichier** `crew/TODO/<slug>.md` → `crew/CURRENT_TASKS/<slug>.md` (`git mv`). Elle disparaît donc du dossier TODO.
- Si la tâche naît directement en cours (pas passée par le backlog), créer le fichier dans `crew/CURRENT_TASKS/`.
- Tant que des actions restent à faire, garder le fichier à jour (cases cochées/non cochées).

### 3. Quand le code d'une tâche est terminé (toutes les actions cochées)
- **Supprimer** le fichier `crew/CURRENT_TASKS/<slug>.md`.
- **Historiser** : ajouter une entrée dans `crew/CLAUDE_CONTEXT/HISTORIQUE.md` (quoi, quand, fichiers/commits clés) — mémoire de contexte du projet.
- **Sortir les tests** : la checklist de validation se range dans **deux sous-dossiers** selon l'exécutant (cf. §4) :
  - `crew/TESTS/IA/<chantier>.md` — tests que **l'IA peut dérouler seule** (🤖 auto pytest/scénario/front, 🔍 config/requête directe : curl, DB, logs, CLI — y compris ciblant un service externe si c'est scriptable).
  - `crew/TESTS/DEV/<chantier>.md` — tests qui **nécessitent vraiment le dev** (🖱️ manuel/visuel navigateur, mobile réel, ou item non outillé pour l'IA).
  - Critère de tri : *« l'IA a-t-elle de quoi l'exécuter elle-même (gain de temps), ou faut-il vraiment l'action humaine ? »*. Si le plugin `playwright` est installé, un scénario navigateur scriptable (parcours, formulaire, responsive) va en `IA/`, pas `DEV/` — `DEV/` reste réservé à ce qui est vraiment non outillable (mobile réel, jugement visuel subjectif). Même chantier → un fichier de chaque côté (mêmes nom + titre), seuls les items diffèrent. Couvrir chemin principal + cas limites (quotas, permissions, erreurs, mobile si UI). **Ne pas cocher** ces tests : validation pour une session ultérieure.

### 4. `crew/TESTS/` — checklists de validation, triées IA / DEV
- **Deux sous-dossiers** : `IA/` (auto-exécutable par l'IA : 🤖 + 🔍) et `DEV/` (action humaine requise : 🖱️ + items non outillés). Un chantier fini → `IA/<chantier>.md` et/ou `DEV/<chantier>.md` (un côté peut être vide s'il n'a aucun item de ce type).
- `INDEX.md` (racine + dans chaque sous-dossier) est régénéré par le hook `crew/crew_hook.py`.
- Cocher les tests quand ils passent ; tous cochés des deux côtés = feature validée. Lorsqu'un fichier de test de `IA/` est entièrement coché/terminé, il est déplacé vers `crew/CLAUDE_CONTEXT/TESTS_DONE/` (et supprimé de `IA/`).

**Règle d'or :** une tâche n'est jamais dans deux dossiers à la fois. Pas commencée → `crew/TODO/` ; commencée → `crew/CURRENT_TASKS/` ; finie → `HISTORIQUE.md` + `crew/TESTS/` (ou `TESTS_DONE/` pour les tests IA validés).

## Batching — parallélisation des tâches (`crew/CLAUDE_BATCH.md`)

Ce fichier indique **quelles tâches peuvent tourner en même temps** : **un batch = un Claude**. On peut lancer un Claude sur le Batch A, un autre sur le Batch B, etc., en parallèle.

**Quand Claude ajoute une tâche au projet, il l'ajoute aussi dans `crew/CLAUDE_BATCH.md`** :
1. Déterminer sa **zone d'impact** (fichiers/modules qu'elle va toucher).
2. Si cette zone **chevauche** celle d'un batch existant, ou si la tâche **dépend** d'une tâche d'un batch → l'ajouter à **ce batch** (un seul Claude, tâches dans l'ordre).
3. Sinon → **nouveau batch** (nouveau workstream parallèle), avec sa ligne `Zone :`.
4. Si la zone n'est pas encore connue (tâche lointaine du backlog), la mettre dans la section **« À classer »** ; elle sera batchée au démarrage.

**Invariant** : les zones de deux batchs **actifs** sont **disjointes** (sinon deux Claudes parallèles entrent en collision). Tâches qui partagent des fichiers → **même batch**.

### Vérification anti-collision avant de démarrer une tâche

Avant de déplacer une tâche vers `crew/CURRENT_TASKS/` (§ Gestion des tâches, point 2), `manager` doit :
1. Identifier la zone de fichiers de la tâche à démarrer.
2. Lister les batchs **actifs** (ayant déjà ≥1 tâche en `crew/CURRENT_TASKS/`) et leur `Zone :` déclarée.
3. Si la zone de la tâche chevauche celle d'un batch actif **autre que le sien** → ne pas démarrer : soit la tâche rejoint ce batch (séquencée après), soit on attend que l'autre batch libère les fichiers concernés. Signaler le conflit au user plutôt que de lancer en silence.
4. Si aucun chevauchement → démarrer normalement.

Garde-fou automatisé (complémentaire, pas suffisant seul) : le hook `crew/crew_hook.py` (`check_zone_overlaps`) compare à chaque tour les `Zone :` de tous les batchs actifs et avertit (non bloquant, stderr) en cas de chevauchement de chemins entre deux batchs actifs différents. Pour une vue à la demande plutôt que d'attendre le prochain `Stop` → `/crew-status`.

Tâche terminée → la retirer de son batch. Le hook `crew/crew_hook.py` avertit (non bloquant) si une tâche TODO/CURRENT n'apparaît nulle part dans `CLAUDE_BATCH.md`, ou si le fichier référence une tâche disparue.

## Efficience de contexte

Ces règles limitent le gaspillage de tokens et les coupures de session prématurées.

### Lectures de fichiers
- **Interdire la lecture complète** d'un fichier de plus de **100 lignes** sans avoir d'abord utilisé grep pour délimiter la zone utile.
- Pour les fichiers très longs (HISTORIQUE.md, graph.json, GRAPH_REPORT.md, lockfiles, migrations) : lire uniquement les tranches pertinentes, jamais le fichier entier.
- Ne jamais coller dans le contexte la sortie complète d'une commande longue (ex. build) : extraire seulement les lignes d'erreur/warning utiles.

### Reset de session
- Après **10 à 12 interactions** ou après chaque tâche terminée, **recommander un `/clear` ou une nouvelle session** à l'utilisateur pour libérer la fenêtre de contexte.
- Si la session approche de la limite et que la tâche n'est pas finie : commit ce qui est fait, noter l'état dans HISTORIQUE ou CURRENT_TASKS, puis suggérer de relancer.

### Guides AGENTS.md segmentés
- Guide global (invariants produit + anti-patterns) : `crew/CLAUDE_CONTEXT/AGENTS.md`
- Un `AGENTS.md` par subtree significatif (ex. `frontend/AGENTS.md`, `backend/AGENTS.md`, `mobile/AGENTS.md`) qui **scope** le fichier racine (le lire, ne pas le dupliquer).
- En session mono-subtree, lire uniquement l'`AGENTS.md` de ce subtree (pas le guide global complet sauf si une règle cross-stack est ambiguë).

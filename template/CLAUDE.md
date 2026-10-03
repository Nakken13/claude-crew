## graphify

Graphe de connaissance dans `graphify-out/` (créé par `graphify init`).

- Questions sur le code : `graphify query "<question>"` d'abord dès que `graphify-out/graph.json` existe ; `graphify path "<A>" "<B>"` pour les relations, `graphify explain "<concept>"` pour un concept.
- `graphify-out/wiki/index.md` (s'il existe) pour la navigation large.
- **Ne jamais lire `graph.json` / `GRAPH_REPORT.md` en entier.**
- Après modification de code : `graphify update .` (AST only, sans coût API).

## Routage des skills

Adapter/retirer les lignes hors stack.

- Architecture/exploration avant lecture brute → `graphify`.
- Nouveau composant/page ou refonte visuelle → `designer` si parcours/specs non tranchés, puis `design-taste-frontend` (obligatoire, anti-slop), `frontend-design`, `ui-ux-pro-max`.
- Audit/retouche d'un écran existant → `impeccable`.
- Animation React Native → `motion-design-rn` + `accessibility-motion` (toujours les deux, reduced-motion obligatoire à chaque animation) ; `haptics` si retour tactile ; `sound-design-ui` seulement si un son est envisagé (défaut : pas de son).
- Chart/graphique → `dataviz` avant le code.
- Bug/test qui échoue → `systematic-debugging` avant tout fix.
- Feature ou fix → `test-driven-development` (test avant code). Feature ambiguë → `brainstorming` d'abord.
- 2+ tâches indépendantes → `dispatching-parallel-agents` ; isolation du workspace → `using-git-worktrees` ; plan avec tâches indépendantes en session → `subagent-driven-development`.
- Auth/tokens/chiffrement/secrets → `security-review` avant merge (`security-guidance` en complément).
- Frontend créé ou retouché : testé responsive (mobile/tablette/desktop) et validé visuellement (`run` puis `playwright` ou `claude-in-chrome`) avant de déclarer fini — un build qui passe ne suffit pas.
- Test navigateur scriptable avec `playwright` → `crew/TESTS/IA`, pas `DEV`.
- Fin de tâche : `requesting-code-review` puis `simplify` avant de committer ; retour de review reçu → `receiving-code-review` ; branche prête → `finishing-a-development-branch`.
- Avant d'affirmer « fait/testé/ça marche » → `verification-before-completion` (lancer réellement les tests). Les diagnostics LSP ne remplacent pas la suite de tests/le build.
- Après modif durable de `CLAUDE.md`/`AGENTS.md`/règles crew → `claude-md-management`.
- LLM/agent : vérifier le provider réel (`grep`) avant `claude-api`.
- Suivi multi-étapes : **`crew/TODO` → `CURRENT_TASKS` → `HISTORIQUE`/`TESTS` est la source unique de vérité** ; ne pas dupliquer avec `writing-plans`/`executing-plans`/`TaskCreate` (réservés aux sessions hors périmètre crew).

## Personas (subagents `.claude/agents/`) — routage obligatoire

Rôles/points de vue (`Agent({subagent_type: "<nom>"})`), pas des procédures techniques. **S'il y a ne serait-ce que 1 % de chance qu'une persona s'applique, la dispatcher — non négociable.**

- Arbitrage business/priorisation/scope, « ça vaut le coup ? » → `ceo` (lecture seule).
- Découpage en tâches, batches, séquencement → `manager` (écrit sous `crew/`).
- **Démarrage d'une tâche existante** (`TODO/` → `CURRENT_TASKS/`) → `manager` aussi, pour l'anti-collision de fichiers (cf. § Batching, cas trivial inclus) — jamais de déplacement de fichier nu.
- Copy marketing/landing/email/ton de marque → `comms` (vérifier `AGENTS.md` pour le ton d'un agent produit).
- Choix technique structurant (2+ approches, refactor maintenant ou plus tard) → `architect` (lecture seule).
- Décision UX/UI (parcours, hiérarchie, rétention, specs chiffrées, conventions plateforme) → `designer` (lecture seule ; retouche d'un écran → `impeccable`).
- Exposition juridique nouvelle (données perso, SDK tiers, paiement, mineurs, IA, contenu utilisateur, scraping, licence, secteur réglementé, nouveau pays) → `legal` (lecture seule) avant de coder.

Rationalisations à rejeter (« c'est rapide », « question simple », « juste un écran », « sûrement aucun enjeu juridique ») → dispatcher quand même. Pas d'implémentation par les personas ; doute entre deux → la plus proche du cœur de la demande.

## Commandes dédiées crew (`/crew-*`)

Exécution outillée du cycle de vie et du batching (procédures dans chaque skill) :

- `/crew-init` — bootstrap du scaffold (une seule fois) ; `/crew-update` — met à jour les fichiers moteur sans toucher aux données.
- `/crew-new-task` — crée une tâche (`TODO/` ou `CURRENT_TASKS/`) avec batching.
- `/crew-start` — reprend ou démarre une tâche (anti-collision, worktree par batch) jusqu'à la clôture.
- `/crew-close-task` — clôture (revue, `simplify`, historique, tests).
- `/crew-status` — rapport lecture seule ; `/crew-count` — batchs lançables en parallèle ; `/crew-dashboard` — dashboard web local.

## Gestion des tâches — cycle de vie unique (modèle par dossiers)

Une tâche = un fichier `.md` qui **se déplace** (`git mv`) ; jamais dans deux dossiers.

```
Problème brut → crew/PROBLEMS/   Pas commencée → crew/TODO/   Parkée → crew/ICEBOX/
Commencée → crew/CURRENT_TASKS/  Bloquée (dev) → crew/PAUSED/
Code fini → crew/CLAUDE_CONTEXT/HISTORIQUE.md + crew/TESTS/{IA,DEV}/<chantier>.md (fichier de tâche supprimé)
Validée → cases cochées ; un test IA entièrement coché → crew/CLAUDE_CONTEXT/TESTS_DONE/
```

Source unique = dossiers `crew/` (un `TODO.md`/`PROBLEMS.md` racine n'est qu'un pointeur).

### 0. `PROBLEMS/` — inbox
Un fichier par bug/friction (`🔴`/`🟡`/`✅`) ; devient une tâche `TODO/` quand planifié.

### 1. `TODO/` — backlog
Uniquement des tâches jamais commencées, actions en `- [ ]`. À l'ajout : catégoriser dans `crew/CLAUDE_BATCH.md`.

### 2. Démarrer → déplacer vers `CURRENT_TASKS/`
Anti-collision obligatoire avant tout déplacement (`manager`, cf. § Batching). Tenir les cases à jour. `ICEBOX/` : jamais démarrée directement, repasser par `TODO/`.

### 2bis. `PAUSED/` — bloquée en attente de validation dev
Tâche déjà démarrée dont la suite dépend d'une action humaine (rendu visuel, device réel, réponse externe) : `git mv` vers `PAUSED/`, retour dans `CURRENT_TASKS/` une fois validée. Compte comme active pour l'anti-collision. Jamais reprise automatiquement par l'IA.

### 3. Code terminé
Supprimer le fichier de `CURRENT_TASKS/`, historiser dans `HISTORIQUE.md`, sortir les tests (`/crew-close-task`). **Ne pas cocher** les tests à ce stade.

### 4. `TESTS/` — checklists IA / DEV
`IA/` : l'IA déroule seule (pytest, `playwright`, curl, DB, logs) ; `DEV/` : action humaine réelle (mobile réel, jugement visuel). Même chantier = un fichier de chaque côté ; chemin principal + cas limites.

**Règle d'or :** pas commencée → `TODO/` ; commencée → `CURRENT_TASKS/` ; bloquée sur validation dev → `PAUSED/` ; finie → `HISTORIQUE.md` + `TESTS/`.

## Batching — parallélisation (`crew/CLAUDE_BATCH.md`)

**Un batch = un Claude** ; plusieurs batchs tournent en parallèle. Toute nouvelle tâche s'ajoute aussi à `CLAUDE_BATCH.md` : zone d'impact connue → batch existant si chevauchement/dépendance, sinon nouveau batch (ligne `Zone :`) ; zone inconnue → « À classer ». Tâche finie → barrer sa ligne (`~~`slug.md`~~`), jamais la supprimer ; un batch entièrement barré est retiré automatiquement par le hook.

**Invariant : les zones de deux batchs actifs (≥1 tâche en `CURRENT_TASKS/` ou `PAUSED/`) sont disjointes** ; fichiers partagés → même batch.

### Vérification anti-collision avant de démarrer une tâche
Si `CURRENT_TASKS/` et `PAUSED/` sont vides, aucun batch actif : le vérifier par listing et démarrer sans `manager`. Sinon `manager` : (1) zone de la tâche ; (2) batchs actifs et leur `Zone :` ; (3) chevauchement avec un autre batch → ne pas démarrer, signaler au user ; (4) sinon démarrer. Le hook Stop avertit (non bloquant) des chevauchements manqués ; `/crew-status` pour une vue à la demande.

## Efficience de contexte

### Lectures de fichiers
**Ne jamais lire en entier un fichier de plus de 100 lignes** sans avoir délimité la zone avec grep (surtout `HISTORIQUE.md`, `graph.json`, lockfiles, migrations). Jamais la sortie complète d'une commande longue : seulement erreurs/warnings.

### Reset de session
- Seuil ~**150k tokens** (session principale) : au-delà, **recommander `/clear` ou une nouvelle session**. Le hook Stop avertit (`systemMessage` ; 150k en fenêtre 200k, 800k en 1M, répétition tous les 50k) mais la règle vaut dès que la conversation semble volumineuse.
- Session proche de la limite, tâche non finie : committer, noter l'état dans `HISTORIQUE`/`CURRENT_TASKS`, suggérer de relancer.
- **Subagents** : ~100k pour l'implémentation (sans descendre sous ~80k) ; ~150k pour les personas lecture seule. Consigne textuelle auto-imposée : au-delà, s'arrêter, produire un **recap** (travail fait, état, fichiers, blocages) et relancer un agent avec ce recap.

### Guides AGENTS.md segmentés
Guide global `crew/CLAUDE_CONTEXT/AGENTS.md` ; un `AGENTS.md` par subtree significatif (le lire seul en session mono-subtree). **`crew/` reste unique à la racine du repo** même si le cwd est un sous-dossier : résoudre la racine (`git rev-parse --show-toplevel`) avant toute écriture `crew/...`, sinon un `crew/` fantôme est créé.

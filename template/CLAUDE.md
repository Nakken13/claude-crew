## graphify

Si `graphify-out/graph.json` existe : `graphify query "<question>"` avant toute lecture brute (`path "<A>" "<B>"`, `explain "<concept>"`) ; `graphify-out/wiki/index.md` pour la vue large ; **jamais** `graph.json`/`GRAPH_REPORT.md` en entier ; `graphify update .` après modif de code (AST, sans coût API). Sinon, ignorer cette section.

## Routage des skills

Adapter/retirer les lignes hors stack.

- Architecture/exploration avant lecture brute → `graphify`.
- UI (adapter à la stack) : nouveau composant/refonte → `designer` si parcours/specs non tranchés, puis `design-taste-frontend` (anti-slop), `frontend-design`, `ui-ux-pro-max` ; audit/retouche d'un écran → `impeccable` ; chart → `dataviz` avant le code ; animation RN → `motion-design-rn` + `accessibility-motion` (reduced-motion obligatoire), `haptics` si tactile, pas de son par défaut.
- Bug/test qui échoue → `systematic-debugging` avant tout fix.
- Feature ou fix → `test-driven-development` (test avant code). Feature ambiguë → `brainstorming` d'abord.
- 2+ tâches indépendantes → `dispatching-parallel-agents` ; isolation du workspace → `using-git-worktrees` ; plan avec tâches indépendantes en session → `subagent-driven-development`.
- Auth/tokens/chiffrement/secrets → `security-review` avant merge (`security-guidance` en complément).
- Frontend créé ou retouché : testé responsive (mobile/tablette/desktop) et validé visuellement (`run` puis `playwright` ou `claude-in-chrome`) avant de déclarer fini — un build qui passe ne suffit pas.
- Test navigateur scriptable avec `playwright` → `crew/TESTS/IA`, pas `DEV`.
- Fin de tâche : `requesting-code-review` puis `simplify` avant de committer **si le diff dépasse ~50 lignes ou touche un fichier moteur/auth/hook** (docs seules, renommage, typo : `verification-before-completion` suffit) ; retour de review reçu → `receiving-code-review` ; branche prête → `finishing-a-development-branch`.
- Avant d'affirmer « fait/testé/ça marche » → `verification-before-completion` (lancer réellement les tests). Les diagnostics LSP ne remplacent pas la suite de tests/le build.
- Après modif durable de `CLAUDE.md`/`AGENTS.md`/règles crew → `claude-md-management`.
- LLM/agent : vérifier le provider réel (`grep`) avant `claude-api`.
- Suivi multi-étapes : **`crew/TODO` → `CURRENT_TASKS` → `HISTORIQUE`/`TESTS` est la source unique de vérité** ; ne pas dupliquer avec `writing-plans`/`executing-plans`/`TaskCreate` (réservés aux sessions hors périmètre crew).

## Personas (`Agent({subagent_type: "<nom>"})`) — routage obligatoire

Rôles, pas procédures ; dispatcher quand la décision a ≥2 options réelles dans le domaine (ou sur demande), jamais pour une réponse évidente. `legal`/`architect` : strictes (doute réel inclus) ; les autres au jugement. Pas d'implémentation par les personas.

`ceo` priorisation/scope · `manager` découpage/batches (écrit sous `crew/`) · `architect` choix technique structurant · `designer` décision UX/UI · `legal` exposition juridique nouvelle (avant de coder) · `comms` copy/ton de marque · `social` distribution réseaux · `seo` visibilité recherche/stores (si surface web publique). Démarrage d'une tâche existante → `/crew-start`, pas `manager`. Critères détaillés : `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md` § Personas.

## Commandes dédiées crew (`/crew-*`)

Exécution outillée du cycle de vie et du batching (procédures dans chaque skill) :

- `/crew-init` — bootstrap du scaffold (une seule fois) ; `/crew-update` — met à jour les fichiers moteur sans toucher aux données.
- `/crew-new-task` — crée une tâche (`TODO/` ou `CURRENT_TASKS/`) avec batching.
- `/crew-start` — reprend ou démarre une tâche (anti-collision, worktree par batch) jusqu'à la clôture.
- `/crew-close-task` — clôture (revue, `simplify`, historique, tests).
- `/crew-status` — rapport lecture seule ; `/crew-count` — batchs lançables en parallèle ; `/crew-dashboard` — dashboard web local ; `/crew-version` — version de crew-mates.

## Tâches, batching, contexte — lire `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md` avant de créer/déplacer une tâche ou d'éditer `CLAUDE_BATCH.md`

Règles toujours actives (détail dans ce doc) :
- Une tâche = un `.md` qui se déplace (`PROBLEMS/`→`TODO/`→`CURRENT_TASKS/`→`PAUSED/`→`HISTORIQUE.md`+`TESTS/`), jamais dans deux dossiers ; jamais de déplacement nu, passer par `/crew-start`. Source unique de vérité = `crew/`.
- Un batch = un Claude ; zones (`Zone :`) des batchs actifs disjointes. Toute nouvelle tâche s'ajoute à `crew/CLAUDE_BATCH.md`.
- Ne jamais lire en entier un fichier > 100 lignes sans délimiter avec grep ; jamais la sortie complète d'une commande longue.
- Conversation volumineuse (~150k tokens) : recommander `/clear` ou une nouvelle session.
- `crew/` unique à la racine du repo : résoudre `git rev-parse --show-toplevel` avant toute écriture `crew/...`.
- Guide global `crew/CLAUDE_CONTEXT/AGENTS.md` ; un `AGENTS.md` par subtree significatif.

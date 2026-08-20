# Scaffold de démarrage projet

Gabarit personnel (référencé depuis `~/.claude/CLAUDE.md`) à copier sur tout
nouveau projet où on veut le même dispositif que sur `voyageo` : routage de
skills, cycle de vie de tâches par dossiers (crew), hooks de sync.

## Bootstrap

Voie rapide : copier ce dossier à la racine du nouveau projet (au moins
`.claude/skills/crew-init/`), ouvrir Claude Code dedans, lancer `/crew-init`
— ce skill fait les étapes 1 à 3 ci-dessous (copie des fichiers restants,
détection stack, questions ciblées, résolution des placeholders,
`check_placeholders.py`) sans qu'il faille les dérouler à la main.

Détail des étapes (ce que `/crew-init` exécute) :

1. Copier dans la racine du nouveau projet : `CLAUDE.md`, `AGENTS.md`,
   `PRODUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.gitignore`,
   `check_placeholders.py`, le dossier `crew/` entier, le dossier
   `.claude/agents/` (personas), `.claude/skills/crew-*` (ces skills
   eux-mêmes, pour disposer de `/crew-new-task`/`/crew-close-task`/
   `/crew-status`/`/crew-start` sur le nouveau projet aussi), et fusionner
   `.claude/settings.json`/`.gitignore` avec ceux du projet s'ils existent
   déjà.
2. Remplacer tous les `<NOM_PROJET>` et `<...>` par les infos réelles du
   projet (stack, repo map, commandes vérifiées) — ne jamais laisser de
   placeholder non résolu dans un fichier livré.
3. Lancer `python check_placeholders.py` à la racine du nouveau projet : un
   bootstrap n'est "fini" que quand cette commande n'affiche rien (exit 0).
   Supprimer `check_placeholders.py` une fois le bootstrap validé (outil de
   scaffold, pas destiné à rester dans le repo final — sauf si tu veux le
   garder en pre-commit).
4. Si le projet a plusieurs subtrees (frontend/backend/mobile/...), dupliquer
   le pattern `AGENTS.md` + `CLAUDE.md` fin (`@AGENTS.md`) dans chaque subtree
   plutôt que de tout mettre à la racine — cf. § "Guides AGENTS.md segmentés"
   dans le `CLAUDE.md` de ce scaffold.
5. Lancer `graphify init` dès que le repo dépasse quelques fichiers (cf. skill
   `graphify`, déclenché par `/graphify`).
6. Adapter la section "Routage des skills" du `CLAUDE.md` à la stack réelle
   du projet (retirer les lignes qui ne s'appliquent pas — ex. `dataviz` si
   pas de dashboard/chart, `motion-design-rn`/`accessibility-motion`/
   `haptics`/`sound-design-ui` si pas de stack React Native/mobile,
   `security-review` reste presque toujours pertinent dès qu'il y a de
   l'auth).

Une fois le projet en route, 4 autres commandes exécutent le cycle de vie
crew au lieu de le dérouler à la main : `/crew-new-task` (créer),
`/crew-close-task` (clôturer), `/crew-status` (rapport lecture seule —
batchs actifs, chevauchements, avancement), `/crew-start` (reprend le
travail sans préciser quoi — continue `CURRENT_TASKS/` ou démarre un
batch `TODO/` inactif). Détail dans le `CLAUDE.md` § "Commandes dédiées
crew".

## Ce qui est toujours inclus (pas de version allégée)

Le système `crew/` (PROBLEMS/TODO/CURRENT_TASKS/TESTS/CLAUDE_CONTEXT + hooks
`crew_hook.py`/`spec_to_task_hook.py`) est copié tel quel sur **tous** les
projets, quelle que soit leur taille — décision explicite : pas de mode light.

## Fichiers de ce scaffold

| Fichier | Rôle |
|---|---|
| `CLAUDE.md` | Comportement Claude Code : routage skills, efficience de contexte, pointeur crew |
| `AGENTS.md` | Stack, repo map, commandes vérifiées — squelette à remplir |
| `PRODUCT.md` | Vision produit / utilisateur cible / scope — à remplir ou supprimer si non pertinent |
| `CONTRIBUTING.md` | Conventions de commit/branche/PR — à remplir ou supprimer si solo sans convention particulière |
| `SECURITY.md` | Limites secrets/auth/PII — à remplir dès qu'il y a de l'auth ou des données sensibles |
| `crew/` | Cycle de vie des tâches par dossiers (dont `ICEBOX/` pour les idées parkées) + hooks de sync |
| `.claude/settings.json` | Hooks pré-cablés (Stop → crew_hook.py, PostToolUse Write → spec_to_task_hook.py, PreToolUse → rappel graphify), fallback `python3`/`python` |
| `.gitignore` | Exclusions courantes (node_modules, .venv, .env, graphify-out/*, état interne crew) |
| `check_placeholders.py` | Garde-fou : liste les `<...>` non résolus après bootstrap |
| `.claude/agents/` | Personas subagents (`ceo`/`manager`/`comms`) — décision business, découpage crew, copy marketing ; à adapter (voix de marque, `<NOM_PROJET>`) |
| `.claude/skills/crew-*` | Commandes `/crew-init`, `/crew-new-task`, `/crew-close-task`, `/crew-status`, `/crew-start` — exécutent le cycle de vie/batching documenté dans `CLAUDE.md`, génériques (pas de placeholder à remplir) |

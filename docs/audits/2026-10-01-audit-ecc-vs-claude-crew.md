# Audit — claude-crew vs plugin ECC 2.2.0 (tokens & réactivité)

Date : 2026-10-01. Objectif : identifier ce qu'ECC fait pour consommer moins
de contexte / répondre plus vite, et ce que claude-crew doit compléter.
Mesures prises sur ce repo (Windows 11, Python 3.12, Node). Les problèmes
constatés sont consignés dans `crew/PROBLEMS/` (un fichier par problème),
les arbitrages viennent du persona `architect`.

## 1. Ordres de grandeur

| | claude-crew | ECC 2.2.0 |
|---|---|---|
| Agents / skills / commandes | 4 (6 sur origin/main) / 8 / 0 | 68 / 286 / 94 |
| CLAUDE.md chargé à chaque session | `template/CLAUDE.md` 2955 mots (~4k tokens) | ~600 mots (3,9 KB) |
| Descriptions frontmatter (toujours chargées) | ~3,4k chars skills + ~1,5k agents | ~80k chars skills + ~10k commandes |
| Entrées hooks | 4 (PreToolUse, PostToolUse Write, Stop, SessionEnd) | 23, consolidées en dispatchers, split sync/async |
| Profil / désactivation des hooks | aucun | `userConfig.hook_profile` minimal/standard/strict + `ECC_DISABLED_HOOKS` |
| Continuité de session | aucune (crew-start relit `crew/` à la main) | SessionStart digest plafonné 8000 chars + PreCompact résumé Haiku |
| Moniteur de contexte | seuil fixe 150k, stderr | seuil scalé fenêtre, répétition 60k, `additionalContext` debouncé |

ECC n'est pas un modèle de sobriété en soi : son listing de skills coûte
~20k tokens par session, GateGuard refuse le premier Edit/Bash par fichier
(un aller-retour supplémentaire à chaque fois, constaté dans cette session),
et `observe` est enregistré deux fois. Ce qu'il faut lui emprunter, ce sont
des **mécanismes**, pas son volume.

## 2. Mesures claude-crew

- Hook PreToolUse (`Bash|Edit|Write|MultiEdit`) : 540-1200 ms par appel
  outil. Démarrage Python nu : 500-1000 ms ; `python -I -S` ~800 ms ; Node
  nu 380-740 ms. **Le coût est le spawn de process, pas le langage** —
  migrer vers Node n'apporterait rien ici.
- Hook Stop : ~740 ms. Doit rester synchrone (peut renvoyer
  `{"decision":"block"}`).
- Faux positif reproduit sur ce repo : `check_batches()` lit `` `CLAUDE.md` ``
  dans la prose d'en-tête de `crew/CLAUDE_BATCH.md` et émet
  « référence une tâche inexistante : `CLAUDE.md` » — dans **tous** les
  projets bootstrapés (l'en-tête vient du template).
- `template/CLAUDE.md` : routage skills 697 mots, cycle de vie 910,
  efficience 457, personas 405, batching 396, commandes 248, graphify 143.
  Les skills `crew-start` et `crew-close-task` ré-encodent déjà
  l'anti-collision et la procédure de clôture : ~1300 mots sont relus deux
  fois à chaque invocation.
- Dérive de repo : le local est **derrière `origin/main`** (personas
  `designer` et `legal` mergées via PR, présentes dans le plugin installé
  0.2.1) et **devant** d'un commit (`89e83da`). À resynchroniser avant tout
  chantier.

## 3. Ce qu'ECC fait et qu'on peut reprendre

Réutilisable tel quel (adapté en Python) :
1. **Gating des hooks** par profil + liste d'ids désactivables, exposé en
   `userConfig` dans `plugin.json` et en variable d'environnement.
2. **SessionStart avec plafond dur** (chars) et interrupteur `off` — borne
   le coût fixe payé à chaque session.
3. **Seuil de compaction lu dans `usage`** du transcript, scalé à la fenêtre
   (160k/200k, 250k/1M), avec intervalle de répétition.
4. **Split sync/async** : tout hook qui ne rend pas de décision bloquante
   passe en `"async": true` (chez nous : SessionEnd, PostToolUse Write).
5. **Accumuler puis agir une fois au Stop** plutôt qu'à chaque edit
   (ECC : format/typecheck ; chez nous : déjà le cas pour l'index/journal,
   à conserver).
6. **Skill d'audit `context-budget`** (prompt-only) : descriptions > 30 mots,
   skills > 400 lignes, CLAUDE.md combiné > 300 lignes, ~500 tokens par
   outil MCP → à proposer comme passe `/crew-status --context` ou dans
   `claude-md-management`.

À ne pas reprendre : GateGuard fact-forcing (friction, +1 tour par fichier),
résumé LLM Haiku en PreCompact (latence synchrone, dépendance CLI, store
hors `crew/`), observe/instincts (lourd, no-op Windows), dispatcher Node
(pas de gain : nos 4 hooks sont déjà un seul script).

## 4. Arbitrages (persona `architect`)

**A. Slimming `template/CLAUDE.md`** → progressive disclosure, cible
1000-1200 mots. Garder en une ligne chaque obligation (schéma d'états +
règle d'or, « démarrer = manager / crew-start, jamais git mv nu »,
invariant zones disjointes, clause personas 1 %, routage skills 1 ligne
par skill, règle des 100 lignes, 150k/100k, `crew/` ancré racine).
Déplacer les procédures détaillées (§0-4, PAUSED, anti-collision en 4
points, nettoyage auto, description du hook) vers les skills `crew-*`
existants — pas de nouveau `RULES.md`. Écarter `.claude/rules` + `paths:`
(règles non path-scopées). Risque : non-adhérence si une obligation perd sa
phrase d'ancrage ; migration des CLAUDE.md déjà personnalisés
(`crew-update`) à arbitrer avec `ceo`. Effort M.

**B. Latence PreToolUse** → pré-filtre shell + marqueur fichier.
`save_locks` écrit/supprime `crew/CLAUDE_CONTEXT/.gate_armed` quand
≥ 2 sessions ; la commande du hook fait `[ -e …/.gate_armed ] || exit 0`
avant de spawner Python (pour `Bash`, laisser passer toujours les claims
`git mv` / `crew-resume:` qui doivent écrire le verrou même en solo).
Spawn évité dans le cas majoritaire (une session) : gain ≈ 0,4-1 s par
appel outil. `CREW_HOOK_PROFILE=minimal` en escape hatch. Effort S/M.

**C. Continuité de session** → hook SessionStart (`startup|resume|compact`)
injectant un digest pur fichier ≤ 2k chars via `additionalContext` :
CURRENT_TASKS/PAUSED (slug, titre, cases), batchs actifs + zones, verrous
d'autres sessions, 3 derniers titres HISTORIQUE, warnings batch. Vue
dérivée, jamais réécrite dans `crew/` (source unique respectée). Remplace
les 3-6k tokens d'outils que `crew-start` dépense à relire l'état. Écarter
PreCompact (redondant : `SessionStart` source `compact` ré-injecte le
digest). Effort S/M.

**D. Moniteur de contexte** → ré-arbitrer `alerte-contexte-150k`
(2026-08-25) : passer de stderr à `{"systemMessage": …}` dans le JSON
Stop, seuil scalé (fenêtre 1M détectée via `model` `[1m]` ou total
> 210k → 800k), répétition tous les 50k avec état par session. Écarter la
détection « 5 outils identiques » (exigerait un PostToolUse par appel,
contraire à B). Effort S.

## 5. Ordre de mise en œuvre conseillé

1. Resynchroniser le repo (`git pull --rebase origin main`).
2. Bug `check_batches` : parser avec `TASK_LINE_RE` (déjà utilisé par
   `prune_closed_batches`) au lieu de la regex générique. Quick win.
3. B — marqueur `.gate_armed` + pré-filtre shell + `async` sur SessionEnd /
   PostToolUse Write. Plus gros gain perçu.
4. D — systemMessage + seuil scalé + intervalle.
5. C — SessionStart digest + simplification de `crew-start` étape 1.
6. A — slimming du template, en dernier (dépend de ce que C/D ajoutent au
   contexte, impose une migration `crew-update`).

Fichiers de problèmes : `crew/PROBLEMS/` (cf. INDEX.md régénéré par le hook).

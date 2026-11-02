# Cycle de vie des tâches, batching et efficience de contexte

Doc lu **à la demande** (déplacé tel quel depuis `CLAUDE.md`, qui ne garde que le routage). À lire avant de créer/déplacer une tâche, toucher `CLAUDE_BATCH.md`, ou en cas de doute sur les seuils de contexte.

## Gestion des tâches — cycle de vie unique (modèle par dossiers)

Une tâche = un fichier `.md` qui **se déplace** (`git mv`) ; jamais dans deux dossiers.

```
Problème brut → crew/PROBLEMS/   Pas commencée → crew/TODO/   Parkée → crew/ICEBOX/
Commencée → crew/CURRENT_TASKS/  Bloquée (dev) → crew/PAUSED/
Code fini → crew/CLAUDE_CONTEXT/HISTORIQUE.md + crew/TESTS/{IA,DEV}/<chantier>.md (fichier de tâche supprimé)
Validée → cases cochées ; un test IA entièrement coché → crew/CLAUDE_CONTEXT/TESTS_DONE/
```

Source unique = dossiers `crew/` (un `TODO.md`/`PROBLEMS.md` racine n'est qu'un pointeur).

### 0-1. `PROBLEMS/` (inbox : un fichier par bug/friction, `🔴`/`🟡`/`✅`) → `TODO/` (backlog : jamais commencées, actions en `- [ ]`, catégorisées dans `crew/CLAUDE_BATCH.md` à l'ajout)

### 2. Démarrer → déplacer vers `CURRENT_TASKS/`
Anti-collision obligatoire avant tout déplacement (`/crew-start`, cf. § Batching). Tenir les cases à jour. `ICEBOX/` : jamais démarrée directement, repasser par `TODO/`.

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
`crew_hook.py next-task` (lancé par `/crew-start`) la fait de façon déterministe : verrous des autres sessions, batchs actifs (`CURRENT_TASKS/`, `PAUSED/`), chevauchement de `Zone :` → candidat écarté, suivant essayé ; rien de démarrable → signaler au user. Démarrage manuel hors `/crew-start` : appliquer les mêmes règles à la main. Le hook Stop avertit (non bloquant) des chevauchements manqués ; `/crew-status` pour une vue à la demande.

## Efficience de contexte

### Lectures de fichiers
**Ne jamais lire en entier un fichier de plus de 100 lignes** sans avoir délimité la zone avec grep (surtout `HISTORIQUE.md`, `graph.json`, lockfiles, migrations). Jamais la sortie complète d'une commande longue : seulement erreurs/warnings.

### Reset de session
- Seuil ~**150k tokens** (session principale) : au-delà, **recommander `/clear` ou une nouvelle session**. Le hook Stop avertit (`systemMessage` ; même seuil 150k quelle que soit la fenêtre (200k ou 1M), répétition tous les 50k) mais la règle vaut dès que la conversation semble volumineuse.
- Session proche de la limite, tâche non finie : committer, noter l'état dans `HISTORIQUE`/`CURRENT_TASKS`, suggérer de relancer.
- **Subagents** : ~100k pour l'implémentation (sans descendre sous ~80k) ; ~150k pour les personas lecture seule. Consigne textuelle auto-imposée : au-delà, s'arrêter, produire un **recap** (travail fait, état, fichiers, blocages) et relancer un agent avec ce recap.

### Guides AGENTS.md segmentés
Guide global `crew/CLAUDE_CONTEXT/AGENTS.md` ; un `AGENTS.md` par subtree significatif (le lire seul en session mono-subtree). **`crew/` reste unique à la racine du repo** même si le cwd est un sous-dossier : résoudre la racine (`git rev-parse --show-toplevel`) avant toute écriture `crew/...`, sinon un `crew/` fantôme est créé.


## Personas — routage détaillé (déplacé de CLAUDE.md)

Rôles/points de vue (`Agent({subagent_type: "<nom>"})`), pas des procédures techniques. Dispatcher une persona quand la décision a ≥2 options réelles dans son domaine, ou que l'utilisateur la demande ; pas pour une question dont la réponse est évidente ou déjà tranchée (chaque dispatch ouvre un subagent complet). Seuil par persona : `legal` et `architect` strictes (déclencheur nouveau ou choix qui engage la suite → dispatcher, et en cas de doute réel sur le caractère « évident » aussi) ; `designer`, `ceo`, `comms`, `social`, `seo` au jugement (≥2 options réelles).

- Arbitrage business/priorisation/scope, « ça vaut le coup ? » → `ceo` (lecture seule).
- Découpage en tâches, batches, séquencement → `manager` (écrit sous `crew/`).
- **Démarrage d'une tâche existante** (`TODO/` → `CURRENT_TASKS/`) → `/crew-start` (son script `next-task` fait l'anti-collision de zones, sans persona) ; `manager` seulement pour classer une tâche sans batch. Jamais de déplacement de fichier nu.
- Copy marketing/landing/email/ton de marque → `comms` (vérifier `AGENTS.md` pour le ton d'un agent produit).
- Choix technique structurant (2+ approches, refactor maintenant ou plus tard) → `architect` (lecture seule).
- Décision UX/UI (parcours, hiérarchie, rétention, specs chiffrées, conventions plateforme) → `designer` (lecture seule ; retouche d'un écran → `impeccable`).
- Exposition juridique nouvelle (données perso, SDK tiers, paiement, mineurs, IA, contenu utilisateur, scraping, licence, secteur réglementé, nouveau pays, influence/jeu-concours/prospection/allégations comparatives) → `legal` (lecture seule) avant de coder.
- Distribution organique sur les réseaux sociaux (plateforme/format, rythme, accroches, pourquoi une vidéo plafonne, plan de test) → `social` (lecture seule ; rend un brief à `comms`).
- Visibilité dans la recherche (Google, stores, réponses d'IA : indexation, mots-clés, schema.org, Core Web Vitals, ASO) → `seo` (lecture seule ; rend un brief à `comms`) — sans surface web publique ni fiche store, ne pas l'invoquer ; réseaux sociaux → `social`.

Pas d'implémentation par les personas ; doute entre deux → la plus proche du cœur de la demande.

**Doublon personas** : `agents/` (source du plugin crew-mates, servi via `${CLAUDE_PLUGIN_ROOT}`) et `.claude/agents/` (copie des projets bootstrapés en mode clone manuel) sont le même contenu ; un projet n'en utilise qu'un seul. Dans ce repo (qui est la source) les deux coexistent par construction ; ne jamais installer le plugin **et** garder `.claude/agents/` dans un projet client (les personas apparaîtraient en double).

---
name: crew-update
description: Met à jour les fichiers "moteur" d'un projet déjà bootstrapé via `/crew-init` vers la dernière version du scaffold (CLAUDE.md/AGENTS.md/PRODUCT.md/CONTRIBUTING.md/SECURITY.md/check_placeholders.py, et en mode legacy crew_hook.py/spec_to_task_hook.py/skills/agents locaux) — sans jamais toucher aux données utilisateur (crew/TODO, CURRENT_TASKS, PROBLEMS, ICEBOX, TESTS, HISTORIQUE.md) ni écraser silencieusement un fichier personnalisé. Trigger — "/crew-update", "mets à jour le scaffold", "récupère les dernières règles crew", "il y a une nouvelle version du scaffold".
---

Ce skill exécute `crew/crew_update.py` (ou `scripts/crew_update.py` en mode
plugin — même module, deux copies comme les autres fichiers moteur de ce
repo). Il ne remplace jamais un fichier sans confirmation explicite.

## Détection du mode d'installation

1. `detect_mode(project_root)` (dans le module, pas seulement en prose ici —
   une seule source de vérité) cherche `.claude/skills/crew-init/SKILL.md`
   dans le projet cible :
   - **Présent** → `"legacy"` (Option C / clone manuel, pré-plugin) :
     `ENGINE_FILES_LEGACY` (`crew_hook.py`, `spec_to_task_hook.py`,
     `.claude/skills/crew-*/SKILL.md`, `.claude/agents/*.md`) est inclus
     automatiquement dans la mise à jour, en plus des fichiers communs. Le
     flag CLI `--legacy` force cette inclusion si la détection se trompe.
   - **Absent** → `"plugin"` : ne PAS tenter de synchroniser skills/agents/
     hooks (ils tournent déjà depuis le plugin installé et se mettent à jour
     via `/plugin update claude-crew` — le dire explicitement à
     l'utilisateur). Seuls les fichiers `ENGINE_FILES_COMMON` sont vérifiés.
   - `plan()`/`--project` fonctionnent dans les deux cas sans intervention
     manuelle ; n'interroger l'utilisateur que si le rapport final montre un
     résultat inattendu (ex. `removed` sur tout `ENGINE_FILES_LEGACY` alors
     que le projet semblait legacy).

## Amorçage (projet legacy sans historique)

2. Si `crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json` n'existe pas encore côté
   projet cible (premier `/crew-update` d'un projet bootstrapé avant
   l'existence de ce mécanisme), tout fichier divergent de la source sortira
   en `conflict` faute de hash enregistré pour prouver l'absence de
   personnalisation — donc rien ne sera appliqué automatiquement au premier
   run. Proposer via `AskUserQuestion` d'amorcer d'abord la baseline :
   "Accepter le contenu local actuel comme non personnalisé depuis notre
   dernière écriture ?" (`seed(project_root, whitelist, version)`, ou
   `python crew_update.py --project <dir> --seed --source-version <version>
   [--legacy]`). C'est un choix de confiance explicite — si l'utilisateur
   refuse, traiter chaque fichier divergent comme un `conflict` normal
   (résolution manuelle un par un, cf. section Confirmation ci-dessous) sans
   amorçage. `seed()` refuse par construction d'écraser un
   `SCAFFOLD_VERSION.json` déjà enregistré (lève une erreur) — ne passer
   `force=True` / `--force` que si l'utilisateur demande explicitement de
   réamorcer volontairement la baseline (ex. après une résolution manuelle
   massive de conflits qu'on veut geler comme nouveau point de départ).

## Résolution de la source

3. Version source du scaffold = champ `version` de
   `.claude-plugin/plugin.json` si accessible (plugin installé ou clone du
   repo scaffold) ; sinon demander à l'utilisateur le chemin de la source
   (clone local du scaffold, ou chemin `${CLAUDE_PLUGIN_ROOT}`) — ne jamais
   deviner un numéro de version.

## Plan (dry-run, jamais d'écriture à ce stade)

4. Appeler `plan(project_root, source_root, whitelist)` (import direct du
   module `crew_update`, ou `python crew_update.py --project <dir> --source
   <dir> [--legacy]` en CLI). Afficher le résultat groupé par statut :
   - `up_to_date` — rien à faire, ne pas lister en détail (juste un compte).
   - `new` — fichier ajouté côté source, absent localement → sera créé.
   - `apply` — fichier inchangé depuis la dernière écriture connue, source a
     évolué → sera mis à jour sans risque de perte.
   - `conflict` — fichier modifié localement depuis la dernière écriture
     connue → **ne sera jamais écrasé silencieusement**. Afficher un diff
     (ou au minimum les deux hashs + les premières lignes différentes) pour
     chacun.
   - `removed` — encore présent localement mais disparu côté source (déplacé
     ou supprimé en amont) → **jamais appliqué automatiquement** (rien à
     copier). Signaler à l'utilisateur pour décision manuelle : vérifier si
     le fichier a été déplacé ailleurs dans la source avant de le supprimer
     soi-même, ne jamais le supprimer silencieusement.

## Confirmation obligatoire

5. **Ne jamais appeler `apply()` sans confirmation explicite.** Utiliser
   `AskUserQuestion` : présenter le résumé (compte par statut + liste des
   fichiers `apply`/`new`/`conflict`), proposer au minimum "Appliquer
   `apply`/`new`, garder les `conflict` tels quels" / "Annuler". Pour chaque
   fichier en `conflict`, l'utilisateur peut choisir "garder ma version"
   (skip, comportement par défaut) — un merge manuel guidé (montrer le diff,
   laisser l'utilisateur éditer) reste possible mais jamais automatique.

## Application

6. Sur confirmation : appeler `apply(project_root, source_root, decisions)`
   puis `record_version(project_root, source_version, decisions)` — bump la
   version enregistrée dans `crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json`
   uniquement pour les fichiers réellement appliqués (les `conflict` gardent
   leur hash enregistré précédent, donc resteront proposés au prochain
   `/crew-update` tant que l'utilisateur ne les a pas résolus).
7. Si seule une partie des fichiers a été appliquée (des `conflict`
   subsistent), le dire explicitement dans le rapport final : la version
   enregistrée avance quand même (elle reflète "ce qu'on a pu synchroniser"),
   mais certains fichiers restent en attente de résolution manuelle.

## Rapporter

8. Résumé final : fichiers créés, fichiers mis à jour, fichiers laissés en
   conflit ou en `removed` (avec rappel qu'ils seront re-proposés au
   prochain `/crew-update` tant qu'ils ne sont pas résolus), nouvelle
   version enregistrée.

## Ce que ce skill ne fait pas

- N'écrit jamais dans `crew/TODO/`, `crew/CURRENT_TASKS/`, `crew/PROBLEMS/`,
  `crew/ICEBOX/`, `crew/TESTS/`, `crew/CLAUDE_CONTEXT/HISTORIQUE.md`,
  `crew/CLAUDE_CONTEXT/TESTS_DONE/`, ni `crew/CLAUDE_BATCH.md` (devient
  donnée live dès le premier batch réel, jamais dans la liste blanche même
  si livré comme squelette au départ).
- N'écrase jamais un fichier `conflict` sans confirmation explicite —
  préfère laisser un fichier périmé plutôt que perdre une personnalisation
  utilisateur.
- Ne bump jamais silencieusement la version sur une application partielle
  sans le signaler dans le rapport.
- Ne tente pas de synchroniser skills/agents/hooks sur un projet en mode
  plugin — redirige vers `/plugin update claude-crew`.

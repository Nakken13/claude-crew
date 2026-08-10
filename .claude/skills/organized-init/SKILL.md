---
name: organized-init
description: Bootstrap le scaffold organized (CLAUDE.md/AGENTS.md/PRODUCT.md/CONTRIBUTING.md/SECURITY.md/organized/) sur un projet neuf ou existant sans ce dispositif — copie les fichiers, détecte la stack, pose les questions nécessaires (vision produit, conventions, secrets), résout les placeholders `<...>`, adapte le routage skills à la stack réelle, lance check_placeholders.py. Trigger — "/organized-init", "initialise le scaffold organized", "bootstrap ce projet avec organized".
---

Ce skill exécute le bootstrap déjà décrit en prose dans le `README.md` du
scaffold (`~/.claude/templates/project-scaffold/`) — il ne remplace pas ce
document, il évite de dérouler les étapes à la main et de laisser un
placeholder non résolu par oubli.

## Détection de l'état actuel

1. Le projet a déjà `CLAUDE.md` + `organized/` remplis (pas de `<...>` restant) →
   ne rien faire, dire à l'utilisateur que le scaffold est déjà initialisé et
   proposer `/organized-status` à la place.
2. Le projet a `CLAUDE.md` + `organized/` avec des placeholders `<...>` non
   résolus → reprendre directement à "Résolution des placeholders" ci-dessous
   (pas besoin de recopier les fichiers).
3. Rien de tout ça → bootstrap complet, étapes ci-dessous depuis le début.

## Étapes

1. **Copier** à la racine du projet (sans écraser un fichier déjà présent et
   déjà rempli) : `CLAUDE.md`, `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`,
   `SECURITY.md`, `check_placeholders.py`, le dossier `organized/` entier,
   `.claude/agents/`, `.claude/skills/organized-*` (ces skills eux-mêmes, pour que
   `/organized-new-task`, `/organized-close-task`, `/organized-status` soient aussi
   disponibles sur le nouveau projet). Fusionner `.gitignore` et
   `.claude/settings.json` avec l'existant s'il y en a déjà un — ne jamais
   écraser des règles/hooks déjà en place, seulement ajouter ce qui manque.
   Si le projet a une stack front (détectée à l'étape suivante) : vérifier
   que le plugin `taste-skill` (skill `design-taste-frontend`, requis par le
   routage skills pour tout composant/page/refonte visuelle) est installé —
   `claude plugin list | grep taste-skill` ; sinon `claude plugin marketplace
   add https://github.com/Leonxlnx/taste-skill` puis `claude plugin install
   taste-skill@taste-skill`.
2. **Détecter la stack réelle** : lire les manifestes présents
   (`package.json`, `requirements.txt`/`pyproject.toml`, `go.mod`,
   `Cargo.toml`, etc.) — jamais de supposition non vérifiée.
3. **Poser via `AskUserQuestion`** ce qui n'est pas déductible du code :
   - Nom du projet, si pas déjà évident depuis un manifeste.
   - Vision produit / utilisateur cible / scope (`PRODUCT.md`) — option
     "outil interne, pas pertinent" → réduire le fichier à une ligne ou le
     supprimer.
   - Convention commits/branches/PR (`CONTRIBUTING.md`) — option "pas de
     convention imposée" → le dire explicitement plutôt que de laisser un
     placeholder.
   - Modèle secrets/auth (`SECURITY.md`) — option "pas d'auth/données
     sensibles" → supprimer le fichier.
4. **Résolution des placeholders** : remplacer tous les `<NOM_PROJET>` et
   `<...>` dans `CLAUDE.md`/`AGENTS.md`/`PRODUCT.md`/`CONTRIBUTING.md`/
   `SECURITY.md` avec les réponses obtenues + la stack détectée. Repo map et
   commandes vérifiées : uniquement des commandes réellement exécutées avec
   succès pendant ce bootstrap, jamais une commande non testée.
5. **Adapter le routage skills** : dans la section "Routage des skills" de
   `CLAUDE.md`, retirer les lignes qui ne s'appliquent pas à la stack
   détectée (ex. lignes React Native/mobile si pas de RN, `dataviz` si pas de
   dashboard/chart).
6. Si le repo dépasse quelques fichiers : lancer `graphify init .`.
7. Lancer `python check_placeholders.py` à la racine. S'il reste des
   placeholders, les résoudre et relancer jusqu'à exit 0.
8. Demander à l'utilisateur s'il veut garder `check_placeholders.py` en
   pre-commit ou le supprimer (c'est un outil de bootstrap, pas destiné à
   rester par défaut une fois le scaffold rempli).
9. **Rapporter** : fichiers créés/remplis, décisions prises (fichiers
   supprimés type `PRODUCT.md`, lignes retirées du routage skills), statut
   final de `check_placeholders.py`.

## Ce que ce skill ne fait pas

- Ne réécrit jamais un `CLAUDE.md`/`AGENTS.md` déjà rempli sans que
  l'utilisateur l'ait demandé explicitement.
- Ne devine pas la stack ou les commandes — lit les manifestes / exécute
  réellement, ne suppose jamais.
- Ne lance pas `graphify init` sur un repo trivial (quelques fichiers) — pas
  utile à cette échelle.

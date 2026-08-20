---
name: crew-init
description: Bootstrap le scaffold crew (CLAUDE.md/AGENTS.md/PRODUCT.md/CONTRIBUTING.md/SECURITY.md/crew/) sur un projet neuf ou existant sans ce dispositif — copie les fichiers, détecte la stack, pose les questions nécessaires (vision produit, conventions, secrets), résout les placeholders `<...>`, adapte le routage skills à la stack réelle, lance check_placeholders.py. Trigger — "/crew-init", "initialise le scaffold crew", "bootstrap ce projet avec crew".
---

Ce skill exécute le bootstrap déjà décrit en prose dans le `README.md` du
scaffold (`~/.claude/templates/project-scaffold/`) — il ne remplace pas ce
document, il évite de dérouler les étapes à la main et de laisser un
placeholder non résolu par oubli.

## Détection de l'état actuel

1. Le projet a déjà `CLAUDE.md` + `crew/` remplis (pas de `<...>` restant) →
   ne rien faire, dire à l'utilisateur que le scaffold est déjà initialisé et
   proposer `/crew-status` à la place.
2. Le projet a `CLAUDE.md` + `crew/` avec des placeholders `<...>` non
   résolus → reprendre directement à "Résolution des placeholders" ci-dessous
   (pas besoin de recopier les fichiers).
3. Rien de tout ça → bootstrap complet, étapes ci-dessous depuis le début.

## Étapes

1. **Copier** à la racine du projet (sans écraser un fichier déjà présent et
   déjà rempli) : `CLAUDE.md`, `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`,
   `SECURITY.md`, `check_placeholders.py`, le dossier `crew/` entier,
   `.claude/agents/`, `.claude/skills/crew-*` (ces skills eux-mêmes, pour que
   `/crew-new-task`, `/crew-close-task`, `/crew-status`,
   `/crew-start` soient aussi disponibles sur le nouveau projet). Fusionner `.gitignore` et
   `.claude/settings.json` avec l'existant s'il y en a déjà un — ne jamais
   écraser des règles/hooks déjà en place, seulement ajouter ce qui manque.
   **Vérifier/installer les dépendances des skills routés dans `CLAUDE.md`** —
   `claude plugin list` ne les liste pas tous, certains manquent silencieusement
   si on ne les checke pas explicitement :
   - Plugins officiels (`claude plugin list | grep -E
     "superpowers|security-guidance|playwright|claude-md-management|frontend-design"`) :
     pour chaque manquant, `claude plugin marketplace add
     anthropics/claude-plugins-official` (idempotent si déjà ajoutée) puis
     `claude plugin install <nom>@claude-plugins-official`.
   - `taste-skill` (skill `design-taste-frontend`) — uniquement si le projet a
     une stack front (détectée à l'étape suivante) : `claude plugin list | grep
     taste-skill` ; sinon `claude plugin marketplace add
     https://github.com/Leonxlnx/taste-skill` puis `claude plugin install
     taste-skill@taste-skill`.
   - `graphify` CLI (nécessaire à `graphify init/update/query`, cf. § graphify
     de `CLAUDE.md`) — vérifier `graphify` sur le PATH ; sinon `pipx install
     graphifyy` (nom du package pip réel, pas `graphify`).
   - `impeccable` et `ui-ux-pro-max` (skills, pas des plugins — utilisés par le
     routage design) — vérifier `~/.claude/skills/impeccable` et
     `~/.claude/skills/ui-ux-pro-max` ; sinon `git clone
     https://github.com/pbakaus/impeccable.git ~/.claude/skills/impeccable` et
     `git clone https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git
     ~/.claude/skills/ui-ux-pro-max`.
   - `motion-design-rn`, `accessibility-motion`, `haptics`, `sound-design-ui`
     (uniquement si le projet a une stack React Native/mobile) — source non
     identifiée à ce jour. Vérifier `~/.claude/skills/<nom>` ; si absent,
     avertir l'utilisateur ("skill non trouvé, source inconnue — le fournir ou
     retirer la ligne RN/mobile du routage") plutôt que d'inventer une
     installation.
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

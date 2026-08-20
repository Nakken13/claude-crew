# Mécanisme de mise à jour du scaffold sur les projets déjà bootstrapés

Ce repo (`organized` / alias public `claude-crew`,
`https://github.com/Nakken13/organized.git`) est le scaffold template source
que `/crew-init` (`.claude/skills/crew-init/SKILL.md`) copie dans un projet
cible (`CLAUDE.md`, `AGENTS.md`, `PRODUCT.md`, `CONTRIBUTING.md`,
`SECURITY.md`, `check_placeholders.py`, `crew/`, `.claude/agents/`,
`.claude/skills/crew-*`).

Problème : une fois copié, aucun mécanisme ne permet de récupérer les mises
à jour ultérieures du template (fix dans `crew_hook.py`, nouvelles règles
CLAUDE.md, nouveaux skills crew-*, etc.) sans tout refaire à la main.
Confirmé par grep : pas de `VERSION`/`CHANGELOG` à la racine, pas de skill
`crew-update`, `crew-init` ne gère que "rien" ou "placeholders non résolus"
— pas "déjà initialisé, version antérieure du template". Le repo étant
public, cette friction touche potentiellement tous ses utilisateurs.

Contrainte forte : une mise à jour ne doit **jamais** écraser les données
utilisateur (`crew/TODO/`, `crew/CURRENT_TASKS/`, `crew/PROBLEMS/`,
`crew/CLAUDE_CONTEXT/HISTORIQUE.md`, `crew/TESTS/`, `crew/ICEBOX/`, etc. du
projet cible). Seuls les fichiers "moteur" (`crew/crew_hook.py`,
`crew/spec_to_task_hook.py`, `check_placeholders.py`,
`.claude/skills/crew-*`, `.claude/agents/*` génériques, sections
structurelles non résolues de `CLAUDE.md`/`AGENTS.md`) sont candidats à la
mise à jour.

Note : à cette étape de planification, seul ce fichier de tâche (et les
fichiers de suivi `crew/` associés) est créé — le contenu ci-dessous décrit
le travail à faire par qui exécutera la tâche ; rien à la racine du repo
(`README.md`, `VERSION`, `CHANGELOG.md`, skill) n'est modifié maintenant.

## Actions

- [ ] Créer un fichier `VERSION` à la racine du scaffold (semver simple,
      ex. `1.0.0`), source unique de vérité pour la version du template.
      Définir la convention de bump (ex. patch = fix hook/skill sans
      changement de structure, minor = nouveau skill/agent/règle, major =
      changement structurel cassant sur `crew/` ou `CLAUDE.md`) et
      documenter cette convention dans `CONTRIBUTING.md`.
- [ ] Créer `CHANGELOG.md` à la racine (format Keep a Changelog ou
      équivalent simple), avec une entrée initiale rétroactive couvrant au
      minimum le renommage `organized/` → `crew/` et le hook auto-commit de
      `hook-auto-commit-cloture-tache.md` si cette tâche est fusionnée avant
      celle-ci (vérifier l'ordre réel au moment de l'implémentation).
- [ ] Décider et documenter (dans la tâche elle-même via une note, ou
      directement en implémentant) : nouveau skill dédié
      `.claude/skills/crew-update/SKILL.md`, ou extension de
      `.claude/skills/crew-init/SKILL.md` pour détecter le cas "déjà
      initialisé, version antérieure" et rediriger vers le flux de mise à
      jour. Trancher selon la complexité réelle du flux (probable : skill
      séparé, pour ne pas alourdir `crew-init` qui reste le cas "premier
      bootstrap").
- [ ] Implémenter la détection de version : lire le `VERSION` du projet
      cible (créé par `crew-init` lors du bootstrap initial — vérifier s'il
      faut aussi rétrofitter un `VERSION` sur les projets déjà bootstrapés
      sans ce fichier, ex. ProjetA/ProjetB/ProjetC/ProjetD/
      ProjetE/ProjetF) vs le `VERSION` du scaffold source
      (`~/.claude/templates/project-scaffold/` ou clone du repo public selon
      comment `crew-init` résout sa source aujourd'hui).
- [ ] Lister la liste blanche des fichiers "moteur" éligibles à la mise à
      jour (cf. contrainte forte ci-dessus) dans le skill lui-même, pour
      qu'elle soit auditable et non ré-inventée à chaque exécution.
      Exclusion explicite et non contournable des dossiers de données
      utilisateur : `crew/TODO/`, `crew/CURRENT_TASKS/`, `crew/PROBLEMS/`,
      `crew/ICEBOX/`, `crew/TESTS/` (hors éventuel `INDEX.md` régénéré par
      le hook, à traiter à part), `crew/CLAUDE_CONTEXT/HISTORIQUE.md`,
      `crew/CLAUDE_CONTEXT/TESTS_DONE/`.
- [ ] Pour chaque fichier moteur candidat : comparer le contenu local à la
      version du scaffold source. Si identique → no-op. Si différent et que
      le fichier local ne porte aucune trace de personnalisation utilisateur
      (heuristique à définir : ex. diff avec la version historique connue
      via le `VERSION` local, ou hash stocké au moment du dernier
      `crew-init`/`crew-update`) → mise à jour directe. Si personnalisation
      détectée → ne jamais écraser silencieusement : afficher un diff et
      proposer soit skip (garder la version locale), soit merge manuel
      guidé (ex. patch/diff affiché à appliquer à la main).
- [ ] Afficher un résumé/diff clair avant application (fichiers ajoutés,
      modifiés, skippés pour cause de personnalisation) et demander
      confirmation avant d'écrire quoi que ce soit sur le disque du projet
      cible — jamais d'application silencieuse.
- [ ] Bumper le `VERSION` du projet cible vers celle du scaffold source une
      fois la mise à jour appliquée (ou vers une version intermédiaire si
      seule une partie des fichiers a été appliquée — documenter ce cas).
- [ ] Mettre à jour `README.md` (racine du scaffold) : nouvelle section
      expliquant comment un utilisateur existant met à jour son projet
      (commande/skill à invoquer), ce qui est touché (liste blanche moteur)
      vs jamais touché (données `crew/`), et comment gérer un conflit de
      personnalisation détecté.
- [ ] Tests si testable : script de simulation (dans `crew/TESTS/IA/` une
      fois la tâche clôturée, ou script utilitaire type
      `crew/test_crew_update.py` si le pattern `test_crew_hook.py` existe
      déjà) qui bootstrappe un projet-cible factice, y ajoute du contenu
      dans `crew/TODO/`, `crew/CURRENT_TASKS/`, `crew/CLAUDE_CONTEXT/HISTORIQUE.md`,
      lance la mise à jour depuis une version antérieure simulée du
      scaffold, et vérifie qu'aucun de ces fichiers de données n'a été
      modifié/écrasé, que les fichiers moteur listés en liste blanche ont
      bien été mis à jour, et qu'un fichier moteur personnalisé n'est pas
      écrasé silencieusement.

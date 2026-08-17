# Historique des tâches terminées

Une entrée par tâche finie (code terminé) : quoi, quand, fichiers/commits
clés. Mémoire de contexte du projet — ne pas résumer, garder les détails qui
aideraient une session future à comprendre pourquoi une décision a été prise.

<!-- Exemple :
## <slug de la tâche> — AAAA-MM-JJ
Quoi : ...
Fichiers/commits clés : ...
-->

## rename-organized-to-crew — 2026-08-17
Quoi : rename complet du système de suivi de tâches `organized` → `crew`
(nom produit affiché : `claude-crew`). Périmètre confirmé avec l'utilisateur :
ce repo + le template global `~/.claude/templates/project-scaffold/`, GitHub
distant non touché pour l'instant (rename local seulement).
Fichiers/commits clés :
- Dossier `organized/` → `crew/` dans ce repo ; `organized_hook.py` →
  `crew_hook.py` (constante Python `ORGANIZED` → `CREW`) ;
  `spec_to_task_hook.py` mis à jour ; `.claude/settings.json` (commandes de
  hooks + patterns de matcher `*organized*` → `*crew*`, `skip=(...,'organized/',...)`
  → `'crew/'`).
- Skills `.claude/skills/organized-{init,new-task,close-task,status,start}`
  renommés en `crew-{init,new-task,close-task,status,start}` (dossiers +
  `name:`/`description`/trigger dans chaque `SKILL.md`).
- `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `check_placeholders.py`,
  `.gitignore`, `.claude/agents/{ceo,manager,architect,comms}.md` mis à jour.
  Note : `README.md` garde intentionnellement les URLs GitHub existantes
  (`github.com/Nakken13/organized`) puisque le remote n'est pas renommé.
- Même rename propagé au template global
  `~/.claude/templates/project-scaffold/` : dossier `ORGA/` → `crew/`,
  `orga_hook.py` → `crew_hook.py` (constante `ORGA` → `CREW`), skills
  `orga-*` → `crew-*`, docs (`CLAUDE.md`, `README.md`, `AGENTS.md`,
  `CONTRIBUTING.md`, `.claude/settings.json`, `.claude/agents/*.md`).
- Grep exhaustif final (`organized|orga_hook|ORGA|orga-`) sur les deux
  arbres : seuls restent les mentions historiques attendues (fichier de
  tâche lui-même, entrées de changelog/index référençant l'ancien nom, URLs
  GitHub conservées).
- Revue : `requesting-code-review` (verdict "with fixes" — seul point relevé
  était la clôture de tâche elle-même, traitée par cette entrée) et
  `simplify` (4 angles : reuse/simplification/efficiency/altitude — aucun
  fix nécessaire, rename mécanique propre).

## readme-github-discoverability — 2026-08-17
Quoi : suite au rename public `organized` → `claude-crew` et à une revue
`comms` sur la découvrabilité GitHub, correction des URLs cassées et
amélioration du copy pour maximiser le taux de star sur le repo public
`Nakken13/claude-crew`. Volet GitHub UI (topics, description du repo, social
preview image) laissé hors scope — reste à faire manuellement dans les
Settings GitHub.
Fichiers/commits clés :
- `README.md` : URLs `Nakken13/organized` → `Nakken13/claude-crew` (badge +
  commande `git clone`) ; badge GitHub stars retiré du haut (peu de stars =
  contre-productif visuellement) et redéplacé en bas près du CTA existant ;
  nouveau CTA court "star ce repo" ajouté juste après le hook d'ouverture
  `## 🧩 The problem`, en plus de celui déjà en fin de fichier.
- `CONTRIBUTING.md` : template NOM_PROJET/placeholders non remplis
  entièrement réécrit avec les conventions réelles du repo solo-maintenu
  (pas de convention de branche imposée, Conventional Commits préférés mais
  pas obligatoires, PR contre `main`, pas de gate CI).
- Revue : `requesting-code-review` (verdict "Ready to merge: Yes", aucun
  Critical/Important — un point Minor sur la formulation de
  `CONTRIBUTING.md` appliqué directement) et `simplify` (4 angles en
  parallèle : reuse/simplification/efficiency/altitude — aucun fix
  nécessaire, diff markdown propre et scopé).

# Empêcher la création de crew/ dans un sous-dossier (frontend/backend)

## Contexte

Bug observé : un dossier `crew/` fantôme se crée parfois dans un sous-dossier
(`frontend/`, `backend/`) au lieu de rester unique à la racine du repo.

**Root cause déjà identifiée** (pas besoin de ré-investiguer) : tous les
chemins `crew/...` référencés dans `.claude/agents/manager.md` et les skills
`crew-new-task`, `crew-close-task`, `crew-init`, `crew-status`, `crew-count`,
`crew-start` sont **relatifs** (ex. `crew/TODO/<slug>.md`), sans jamais
ancrer explicitement à la racine du repo. Or `CLAUDE.md` § « Guides
AGENTS.md segmentés » décrit un usage normal en session mono-subtree
(`frontend/AGENTS.md`, `backend/AGENTS.md`) — si la session/l'agent
travaille avec un cwd dans un sous-dossier, un `Write` sur un chemin relatif
`crew/...` crée un `crew/` dupliqué sous ce sous-dossier au lieu de la
racine.

Pour comparaison, `scripts/crew_hook.py` (ligne ~40) résout déjà
correctement sa racine via
`ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parent.parent)`
— le hook n'a pas ce bug, seuls les skills/persona qui écrivent des
fichiers `crew/` via des chemins relatifs l'ont.

## Zone d'impact

`.claude/agents/manager.md` ; `.claude/skills/crew-new-task/SKILL.md`,
`.claude/skills/crew-close-task/SKILL.md`, `.claude/skills/crew-init/SKILL.md`,
`.claude/skills/crew-status/SKILL.md`, `.claude/skills/crew-count/SKILL.md`,
`.claude/skills/crew-start/SKILL.md` ; `CLAUDE.md` § Guides AGENTS.md
segmentés / § Gestion des tâches.

Cette passe ne touche pas de code hors `crew/` (pas de fix applicatif ici,
juste l'encodage de la tâche + investigation/nettoyage).

## Actions

- [ ] Confirmer le bug en reproduisant (lancer une tâche crew depuis un cwd
      de sous-dossier type `frontend/`, vérifier si un `crew/` apparaît là)
- [ ] Ajouter dans `.claude/agents/manager.md` une consigne explicite :
      toujours résoudre `crew/...` depuis la racine du repo (ex.
      `git rev-parse --show-toplevel` ou équivalent), jamais relatif au cwd
      courant
- [ ] Appliquer la même consigne aux skills `crew-new-task`, `crew-close-task`,
      `crew-init`, `crew-status`, `crew-count`, `crew-start` (SKILL.md)
- [ ] Vérifier/documenter dans `CLAUDE.md` § Guides AGENTS.md segmentés que
      le travail mono-subtree ne doit jamais faire dériver l'emplacement de
      `crew/` (rester unique à la racine même en scope frontend/backend)
- [ ] Chercher et nettoyer manuellement tout `crew/` fantôme déjà présent
      dans des sous-dossiers de ce repo ou d'autres projets connus (audit
      rapide, ne pas supprimer sans vérifier le contenu d'abord)

---
name: crew-status
description: Rapport lecture seule de l'état crew — batchs actifs et zones, tâches en cours, tests IA non cochés, TODO non classées. Trigger — "/crew-status", "où en est le projet", "état des batchs".
---

Skill lecture seule — ne modifie aucun fichier. Complète le hook `Stop`
(`crew/crew_hook.py`, sortie discrète en stderr) par une vue à la demande,
en session.

**Ancrage racine obligatoire** : tout chemin `crew/...` de ce skill se
résout **depuis la racine du repo**, jamais depuis le cwd courant. En
session mono-subtree (cf. `CLAUDE.md` § Guides AGENTS.md segmentés), le cwd
peut être un sous-dossier — un chemin relatif `crew/...` lu tel quel
risquerait de rater le vrai `crew/` à la racine. Résoudre la racine une
seule fois en début d'exécution (`git rev-parse --show-toplevel` ou
équivalent) si elle n'est pas déjà connue — pas besoin de revérifier à
chaque `Read`/`Bash` suivant.

## Ce qu'il rapporte

1. **Batchs actifs** (`crew/CLAUDE_BATCH.md`) : liste des batchs ayant ≥1
   tâche en `crew/CURRENT_TASKS/`, leur `Zone :` déclarée, et tout
   chevauchement de zone détecté entre deux batchs actifs différents —
   invariant violé, à signaler explicitement, pas juste à lister en
   passant.
2. **Tâches en cours** (`crew/CURRENT_TASKS/*.md`) : pour chacune, ratio
   actions cochées / total.
2bis. **Tâches en pause** (`crew/PAUSED/*.md`) : lister nommément, chacune
   en attente d'une validation visuelle/dev par l'utilisateur — à signaler
   explicitement, ne pas les compter comme du travail en cours normal.
3. **Tests IA non cochés** (`crew/TESTS/IA/*.md`) : fichiers avec au moins
   une case non cochée — ce qui reste à valider.
4. **Tâches TODO orphelines** : présentes dans `crew/TODO/` mais absentes de
   `crew/CLAUDE_BATCH.md` (ni batch, ni section « À classer »).
5. **Bootstrap** : si `check_placeholders.py` existe encore à la racine, le
   lancer et inclure son résultat — des placeholders `<...>` restants
   signifient que le scaffold n'est pas encore totalement initialisé
   (renvoyer vers `/crew-init`).
6. **Worktrees de batch orphelins** (`git worktree list`, filtrer les
   entrées `../<nom-repo>-batch-*`) : pour chacun, vérifier qu'une session
   dans `crew/CLAUDE_CONTEXT/crew_lock.json` porte bien ce chemin comme
   `worktree`. Un worktree présent sur disque sans entrée session
   correspondante = crash ou `/crew-close-task` jamais lancé pour ce batch —
   le signaler nommément pour nettoyage manuel (`git worktree remove` /
   `git branch -d` par l'utilisateur), ne jamais le supprimer soi-même
   (pourrait contenir du travail non commité).

## Format de sortie

Compact, une ligne par item, pas de paragraphe répété à chaque run. Gabarit
(sections omises si vides, sauf mention contraire) :

```
🟢 Batchs actifs
- <nom> — Zone : <chemins> — X tâche(s) restante(s)

⚠️ Chevauchements
- <nom> ↔ <nom> sur <chemin commun>

⏳ En cours
- <slug> — <n>/<m> actions cochées

⏸️ En pause
- <slug> — bloqué, validation dev en attente

📝 Tests IA non cochés (N fichiers)
- <fichier>

🗑️ TODO orphelines
- <slug>

🧹 Worktrees orphelins
- <path> (aucune session ne le référence)

⚠️ Bootstrap : N placeholder(s) <...> restant(s) — voir /crew-init
```

Une section sans item n'apparaît pas (sauf "Batchs actifs"/"En cours" : si
vide, une ligne `(aucun)` suffit — évite de faire croire à un rapport
tronqué). `⚠️ Chevauchements` est calculé une seule fois (même comparaison
que dans "Ce qu'il rapporte" point 1), une ligne par paire en conflit — pas
de duplication sous chaque batch concerné. La ligne "En pause" reste
générique (pas de lecture du contenu du fichier `crew/PAUSED/<slug>.md` :
sa raison est déjà `crew/PAUSED/README.md`/`CLAUDE.md` § 2bis — toujours
"attend une validation visuelle/dev").

## Ce que ce skill ne fait pas

- N'écrit, ne déplace, ne coche aucun fichier — pur reporting.
- Ne remplace pas `/crew-new-task` ou `/crew-close-task` pour agir sur une
  tâche — sert seulement à avoir une vue avant de décider quoi faire.
- Ne supprime jamais automatiquement un worktree orphelin — signale
  seulement, le nettoyage reste une décision manuelle de l'utilisateur.

---
name: crew-start
description: Reprend le travail crew sans que l'utilisateur précise quoi — continue la (ou les) tâche(s) déjà en crew/CURRENT_TASKS/ si il y en a ; sinon démarre un batch pas encore actif depuis crew/TODO/ (anti-collision via manager) puis code. Trigger — "/crew-start", "continue le travail", "reprends où t'en étais", "lance la suite", "qu'est-ce qu'on fait maintenant".
---

Point d'entrée unique pour reprendre une session crew sans avoir à dire
quelle tâche. Combine `/crew-status` (lecture), le protocole de
démarrage (`CLAUDE.md` § "Gestion des tâches" point 2 + § "Batching") et
l'implémentation elle-même — jusqu'à `/crew-close-task` en fin de
tâche.

## Étapes

1. **Lire l'état** : lister `crew/CURRENT_TASKS/*.md` (hors
   `INDEX.md`/`README.md`).

### Cas A — `crew/CURRENT_TASKS/` non vide

2A. Une seule tâche → c'est elle qu'on reprend.
    Plusieurs tâches → elles appartiennent forcément au même batch actif
    (invariant de disjonction, cf. `CLAUDE.md` § Batching) ou à des batchs
    actifs différents déjà lancés en parallèle par l'utilisateur : prendre
    celle qui a le plus d'actions déjà cochées (la plus avancée) ; en cas
    d'égalité, demander à l'utilisateur laquelle prioriser plutôt que
    deviner.
2A-bis. **Verrou live obligatoire avant de commencer à éditer** : exécuter
    `Bash({command: ': "crew-resume:<slug>.md"'})` (no-op, aucun effet de
    bord — sert uniquement à faire passer l'intention au hook `PreToolUse`).
    Une tâche déjà en `CURRENT_TASKS/` n'a jamais transité par un `git mv`
    pendant cette session : sans cette étape, une autre session qui reprend
    la même tâche au même moment ne serait jamais détectée (le verrou
    historique ne se pose qu'au moment du `git mv` TODO→CURRENT_TASKS, cf.
    Cas B ci-dessous). Si le hook bloque (exit 2, message « déjà repris par
    une autre session ») → NE PAS continuer sur cette tâche : rapporter le
    conflit à l'utilisateur et s'arrêter (ou choisir une autre tâche d'un
    batch différent si le contexte le permet). Pas de blocage → poursuivre
    normalement.
3A. Relire le fichier de la tâche choisie, reprendre les actions `- [ ]`
    non cochées dans l'ordre. Appliquer les skills normalement pertinents
    au travail lui-même (`test-driven-development`, `systematic-debugging`,
    `graphify`, etc. — cf. § Routage des skills de `CLAUDE.md`) : ce skill
    ne remplace pas ce routage, il sert juste à ne pas avoir à (re)choisir
    la tâche.
4A. Cocher chaque action au fur et à mesure qu'elle est réellement finie
    (pas en avance, pas en lot à la fin).
5A. Toutes les actions cochées → enchaîner directement sur le skill
    `crew-close-task` (ne pas s'arrêter avant, ne pas demander
    confirmation pour cette étape-là, elle fait partie du protocole).

### Cas B — `crew/CURRENT_TASKS/` vide

2B. Lire `crew/CLAUDE_BATCH.md` : lister les batchs, et parmi eux ceux
    **actifs** (≥1 tâche déjà en `CURRENT_TASKS/` — donc aucun ici par
    définition puisqu'on est dans le cas B, sauf tâche d'un autre batch
    lancée hors de ce skill : revérifier quand même). Un batch **inactif**
    = pas de tâche en cours nulle part pour lui.
3B. Choisir le premier batch inactif qui a au moins une tâche listée dans
    `crew/TODO/` (ordre d'apparition dans `CLAUDE_BATCH.md` = priorité
    par défaut ; si l'utilisateur a une préférence explicite en tête pour
    cette session, la respecter à la place). Ignorer la section « À
    classer » (zone d'impact inconnue = pas prêt à démarrer) et
    `crew/ICEBOX/` (jamais démarré directement, cf. `CLAUDE.md`).
    Aucun batch avec tâche TODO dispo → le dire à l'utilisateur et
    s'arrêter (rien à démarrer automatiquement).
4B. Dans ce batch, prendre la **première** tâche listée (ordre du batch =
    séquencement voulu).
5B. **Vérification anti-collision obligatoire** avant tout déplacement :
    dispatcher `Agent({subagent_type: "manager"})` avec la tâche + son
    batch, pour confirmer que sa zone de fichiers ne chevauche aucun batch
    actif différent (cf. `CLAUDE.md` § Batching). Chevauchement détecté →
    ne pas démarrer, rapporter le conflit à l'utilisateur et s'arrêter.
6B. Pas de conflit → `git mv crew/TODO/<slug>.md
    crew/CURRENT_TASKS/<slug>.md`, mettre à jour les deux `INDEX.md`.
7B. Poursuivre en Cas A à partir de l'étape 3A (implémentation, cases
    cochées au fur et à mesure, `crew-close-task` en fin de tâche).

## Ce que ce skill ne fait pas

- Ne démarre jamais deux tâches de batchs différents dans la même
  invocation — un `/crew-start` = une tâche jusqu'à sa clôture (ou
  jusqu'à blocage réel).
- Ne pioche jamais dans `crew/ICEBOX/` ni dans la section « À
  classer » de `CLAUDE_BATCH.md` — ces tâches ne sont pas prêtes à être
  démarrées automatiquement.
- Ne coche pas d'actions non réellement terminées pour avancer plus vite.
- Ne saute pas la vérification anti-collision `manager` avant un
  déplacement TODO → CURRENT_TASKS, même si un seul batch semble actif.
- Ne remplace pas `/crew-close-task` — l'appelle en fin de tâche
  plutôt que de dérouler la clôture à la main.

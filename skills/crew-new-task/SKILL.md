---
name: crew-new-task
description: Crée une nouvelle tâche crew (backlog TODO ou démarrage direct en CURRENT_TASKS) en appliquant le protocole complet du cycle de vie crew — fichier de tâche, INDEX.md, catégorisation CLAUDE_BATCH.md — via un prompt standardisé au persona manager. Trigger — "/crew-new-task", "crée une tâche", "ajoute au backlog", "nouvelle feature à planifier", "découpe ça en tâches".
---

Ce skill encode le protocole de création de tâche déjà défini dans
`CLAUDE.md` (§ Gestion des tâches, § Batching) — il ne remplace pas ce
document, il évite de ré-écrire à la main un prompt long à chaque fois.
Source unique de vérité = `CLAUDE.md`, ce fichier ne fait que standardiser
l'appel.

## Ce que fait ce skill

1. Rassembler le contexte disponible sur la demande : quoi, pourquoi,
   contexte technique connu (fichiers/écrans/modules concernés si
   identifiables, dépendances cross-repo si ce projet en a — autre
   repo backend/frontend séparé, service partagé), et si la tâche démarre
   tout de suite (`CURRENT_TASKS/`) ou va au backlog (`TODO/`).
2. Si `.claude/agents/manager.md` existe : dispatcher **un seul**
   `Agent({subagent_type: "manager"})` avec un prompt qui couvre
   explicitement, dans l'ordre :
   - description de la feature/tâche + contexte (pourquoi, dépendances
     connues) ;
   - découpage en actions cochables `- [ ]` concrètes (pas vagues) ;
   - où le fichier naît (`crew/TODO/<slug>.md` ou
     `crew/CURRENT_TASKS/<slug>.md`) ;
   - mise à jour de l'`INDEX.md` du dossier concerné ;
   - catégorisation dans `crew/CLAUDE_BATCH.md` : zone d'impact,
     rattachement à un batch existant si chevauchement, sinon nouveau batch
     ou section « À classer » ; vérifier l'invariant de disjonction entre
     batchs actifs ;
   - consigne explicite : ne toucher à aucun fichier hors `crew/`.
   Si la persona `manager` n'existe pas dans ce projet (scaffold partiel),
   exécuter directement les mêmes étapes en suivant `CLAUDE.md`.
3. Rapporter à l'utilisateur : chemin du fichier créé, résumé des actions
   cochables, batch/section d'atterrissage, et toute dépendance externe
   (cross-repo, séquencement) signalée.

## Gabarit de prompt pour l'agent manager

```
Nouvelle tâche à ajouter au backlog crew.

<description de la feature/du problème, contexte, pourquoi>

Contexte technique connu :
<fichiers/modules concernés si connus, dépendances cross-repo si ce projet
en a, tâches crew existantes à regarder pour convention/infra proche>

Ce qu'il faut faire, en suivant strictement le cycle de vie décrit dans
CLAUDE.md :
1. Crée <crew/TODO/<slug>.md | crew/CURRENT_TASKS/<slug>.md> avec description
   + actions cochables `- [ ]` concrètes.
2. Découpe en sous-actions réalistes (lister les axes attendus si connus).
3. Mets à jour l'INDEX.md du dossier concerné.
4. Catégorise dans crew/CLAUDE_BATCH.md (zone d'impact, batch existant si
   chevauchement, sinon nouveau batch ou "À classer"). Vérifie l'invariant de
   disjonction entre batchs actifs.
5. Ne touche à aucun fichier hors crew/.

Rapporte : chemin du fichier créé, résumé des actions cochables choisies,
et batch/section d'atterrissage dans CLAUDE_BATCH.md.
```

## Ce que ce skill ne fait pas

- Ne décide pas de priorité/scope business à la place de la persona `ceo`
  (si elle existe dans ce projet) — si la demande est une décision produit
  ambiguë plutôt qu'un pur découpage, router vers `ceo` d'abord.
- N'écrit jamais de code — uniquement des fichiers `crew/`.
- Ne duplique pas une tâche existante : vérifier d'abord
  `crew/TODO/INDEX.md` et `crew/CURRENT_TASKS/INDEX.md`.

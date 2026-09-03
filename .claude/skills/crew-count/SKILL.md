---
name: crew-count
description: Rapport lecture seule — combien de batchs de crew/CLAUDE_BATCH.md sont lançables en parallèle maintenant (un Claude par batch), en distinguant batchs déjà actifs, encore lançables, et exclus pour chevauchement de zone. Trigger — "/crew-count", "combien de batchs je peux lancer", "combien de Claude en parallèle".
---

Skill lecture seule — ne modifie aucun fichier. Répond directement à
« combien de batchs puis-je lancer en parallèle maintenant ? » au lieu de
laisser l'utilisateur deviner à l'aveugle depuis `crew/CLAUDE_BATCH.md`.
Complète `/crew-status` (qui donne une vue d'ensemble) par un chiffre
actionnable.

## Méthode

1. Parser `crew/CLAUDE_BATCH.md` — si le fichier dépasse 100 lignes, grep
   d'abord sur `## Batch`/`Zone :` pour scoper la lecture plutôt qu'un Read
   intégral (règle § Efficience de contexte de `CLAUDE.md` racine). Garder
   en mémoire la liste batch → zone → tâches extraite ici : les étapes
   suivantes la réutilisent, pas de reparsing. Ignorer la section
   **« À classer »** — zone d'impact inconnue, donc pas lançable en
   parallèle sans risque de collision.
2. Ignorer tout batch dont le nom, la `Zone :` ou l'une de ses tâches
   listées contient encore un placeholder `<...>` non résolu (ex.
   `Batch A` / `Zone : <fichiers/modules>` / `<slug>.md` du gabarit initial
   de `crew/CLAUDE_BATCH.md`) — c'est du bruit de template, pas une tâche
   réelle. Le signaler séparément (« placeholder non résolu, ignoré ») sans
   le compter nulle part.
3. Pour chaque batch nommé restant (`## Batch <nom>`) :
   - lister ses tâches (items numérotés/à puces sous le titre) ;
   - une tâche barrée (`~~slug.md~~`) est **clôturée** — convention
     § Batching/« Nettoyage automatique » de `CLAUDE.md` racine — ne
     compte pas ;
   - un batch **sans tâche restante** (toutes barrées ou liste vide) ne
     compte pas du tout, ni comme actif ni comme lançable.
4. Lister une seule fois `crew/CURRENT_TASKS/*.md` (un Glob/listing, pas un
   Read par slug) puis, pour chaque batch avec ≥1 tâche restante, comparer
   ses slugs restants à cette liste en mémoire (pas seulement le texte du
   batch, qui peut être périmé) :
   - **actif** : même critère que « batch actif » dans `crew-status` (≥1
     tâche du batch présente dans `crew/CURRENT_TASKS/`) → déjà en cours,
     pas disponible pour du parallélisme *supplémentaire*.
   - **lançable** : ≥1 tâche restante mais aucune présente dans
     `crew/CURRENT_TASKS/` (encore en `crew/TODO/` ou nulle part
     matérialisée) → prêt à donner à un nouveau Claude.
5. Vérifier l'invariant de disjonction de zones sur les zones déjà extraites
   à l'étape 1 (pas de reparsing) — comparaison par paire de chemins, même
   principe que le `check_zone_overlaps` de `crew-status`/`crew_hook.py`,
   mais étendu ici à **actifs + lançables** (`crew-status` et le hook ne
   comparent qu'actif contre actif ; `crew-count` doit aussi détecter
   qu'un batch lançable chevaucherait un batch déjà actif ou un autre
   lançable, sinon le compte de parallélisme serait faux). Si deux
   `Zone :` se chevauchent, les batchs concernés ne sont **pas** sûrs à
   paralléliser entre eux — les exclure du compte "lançable en parallèle
   sûr" et le signaler nommément plutôt que de les compter.

## Format de sortie

Compact, une ligne par batch, pas de paragraphe explicatif répété à chaque
run. Gabarit :

```
## N lançable(s) en parallèle

🚀 Lançables
- <nom> — Zone: <chemins> — X tâche(s) restante(s)

🟢 Déjà actifs (non comptés)
- <nom> — Zone: <chemins> — X tâche(s) restante(s)

⛔ Exclus (chevauchement)
- <nom> ↔ <nom> sur <chemin commun>

📋 À classer (ignoré) : N tâche(s)
```

Règles :
- Le chiffre de tête = uniquement les batchs "lançables" (zones disjointes
  entre eux et vs actifs).
- Sections **🟢**/**⛔**/**📋** omises si vides (pas de titre "0 batch" à
  rallonge) — sauf **🚀** : si 0 lançable, garder `## 0 lançable(s) en
  parallèle` et ajouter en une ligne la raison la plus visible (tout actif /
  tout clôturé / tout en « À classer »).
- Un chevauchement se signale sur la ligne `⛔` elle-même (batchs + chemin
  commun), pas dans un paragraphe séparé.

## Ce que ce skill ne fait pas

- N'écrit, ne déplace, ne coche aucun fichier — pur reporting.
- Ne démarre aucune tâche à la place de `manager`/`/crew-start` — donne le
  chiffre et la liste, la décision de lancer reste à l'utilisateur.
- Ne recatégorise pas les tâches de la section « À classer » — signale
  seulement qu'elles existent et ne sont pas comptées.

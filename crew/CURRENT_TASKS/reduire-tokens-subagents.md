# Réduire la consommation de tokens des subagents

## Contexte

Les subagents (personas `.claude/agents/*.md` : architect, ceo, manager, comms ;
plus tout agent dispatché via le tool Agent/Task depuis les skills crew et
ailleurs) consomment trop de tokens sur ce projet. Causes suspectées : prompts
de dispatch trop verbeux, contexte dupliqué transmis à l'agent au lieu de le
laisser lire lui-même, sur-lecture de fichiers entiers au lieu de grep ciblé,
agents dispatchés alors qu'ils ne sont pas nécessaires, absence de garde-fou
concret sur la profondeur/volume de contexte transmis.

La règle "Efficience de contexte" de `CLAUDE.md` (seuil ~150k, interdiction de
lecture complète >100 lignes sans grep, auto-arrêt + recap pour subagents)
existe déjà mais semble insuffisante en pratique — à vérifier pourquoi
(non appliquée ? pas assez contraignante ? pas rappelée au bon endroit ?).

## Actions

- [x] Auditer les prompts de dispatch des skills `crew-new-task`,
      `crew-close-task`, `crew-status`, `crew-count`, `crew-start` : taille de
      chaque prompt, contexte redondant avec ce que l'agent peut lire
      lui-même (fichiers déjà accessibles, historique déjà dans crew/).
      Résultat : `crew-status`/`crew-count` ne dispatchent aucune persona
      (pur reporting direct) — rien à réduire là. `crew-close-task` invoque
      des skills (`requesting-code-review`, `simplify`), pas de persona — rien
      à réduire non plus. `crew-new-task` avait un gabarit de 24 lignes qui
      réexpliquait le cycle de vie déjà encodé dans `manager.md` lui-même
      (redondance directe). `crew-start` dispatchait `manager` de façon
      inconditionnelle à l'étape 5B même quand aucun batch n'est actif
      (vérifiable par un simple listing).
- [x] Vérifier que les personas `.claude/agents/architect.md`, `ceo.md`,
      `manager.md`, `comms.md` respectent la règle grep-avant-lecture-complète
      de `CLAUDE.md`. Résultat : aucune des 4 ne la mentionnait explicitement
      — corrigé (ligne ajoutée dans chacune, + copies packagées `agents/*.md`).
- [x] Identifier dans les skills crew-* et le routage `CLAUDE.md` § Personas
      les cas où un agent est dispatché alors qu'une réponse directe (sans
      subagent) suffirait. Cas concret trouvé et corrigé : `crew-start` étape
      5B dispatchait `manager` même quand `CURRENT_TASKS/`+`PAUSED/` sont vides
      (aucun chevauchement possible par définition) — exception ajoutée à
      `CLAUDE.md` § Personas + § Batching + `crew-start/SKILL.md`.
- [x] Réduire/resserrer les prompts de dispatch, en particulier
      `crew-new-task` et `crew-close-task`. `crew-new-task` : gabarit réduit de
      24 à ~9 lignes (délègue au rôle déjà encodé dans `manager.md` au lieu de
      le réexpliquer). `crew-close-task` : pas de gabarit de dispatch persona
      à réduire (confirmé ci-dessus).
- [x] Vérifier concrètement pourquoi la règle "Efficience de contexte"
      existante ne suffit pas. Cause identifiée : pour les subagents, la règle
      n'a aucun mécanisme automatique (contrairement au hook Stop de la
      session principale) et n'était pas répétée dans les fichiers personas
      eux-mêmes — une règle globale non rappelée au point d'usage est plus
      facilement oubliée par un agent qui démarre à froid.
- [x] Documenter dans `CLAUDE.md` si une règle plus stricte est nécessaire.
      Ajouté : exception de dispatch (§ Personas + § Batching), seuil
      différencié par rôle et garde-fou "éviter le dispatch quand une
      vérification directe suffit" (§ Efficience de contexte).
- [x] Mesurer/comparer avant-après si possible. Donnée mesurée en session :
      le dispatch `manager` évitable (anti-collision sur batchs 100% vides) a
      coûté ~25k tokens / 14s / 2 tool_uses pour une réponse à une question
      tranchable par un listing direct — cas désormais éliminé par
      l'exception ajoutée.
- [x] Évaluer un seuil de fenêtre de contexte plus bas pour les subagents
      (~100k au lieu de ~150k), différencié par rôle. Documenté dans
      `CLAUDE.md` § Efficience de contexte : ~100k pour les agents
      d'implémentation, pas de resserrement pour les personas read-only déjà
      courtes, plancher ~80k pour éviter que l'overhead recap/relaunch
      n'annule le gain.

## Zone d'impact

`.claude/agents/*.md` ; `.claude/skills/crew-new-task/SKILL.md`,
`.claude/skills/crew-close-task/SKILL.md`,
`.claude/skills/crew-status/SKILL.md`, `.claude/skills/crew-count/SKILL.md`,
`.claude/skills/crew-start/SKILL.md` (prompts de dispatch uniquement) ;
`CLAUDE.md` § Personas / § Efficience de contexte.

**Chevauchement connu** avec la tâche `condenser-crew-count-status.md` sur
`.claude/skills/crew-count/SKILL.md` et `.claude/skills/crew-status/SKILL.md`
— même batch, cette tâche passe en premier sur ces deux fichiers (trim des
prompts de dispatch) avant que l'autre tâche ne retouche le format de sortie.

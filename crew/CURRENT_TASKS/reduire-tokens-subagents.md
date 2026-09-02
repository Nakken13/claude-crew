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

- [ ] Auditer les prompts de dispatch des skills `crew-new-task`,
      `crew-close-task`, `crew-status`, `crew-count`, `crew-start` : taille de
      chaque prompt, contexte redondant avec ce que l'agent peut lire
      lui-même (fichiers déjà accessibles, historique déjà dans crew/)
- [ ] Vérifier que les personas `.claude/agents/architect.md`, `ceo.md`,
      `manager.md`, `comms.md` respectent la règle grep-avant-lecture-complète
      de `CLAUDE.md` (pas de lecture systématique de fichiers longs type
      HISTORIQUE.md, CLAUDE_BATCH.md en entier)
- [ ] Identifier dans les skills crew-* et le routage `CLAUDE.md` § Personas
      les cas où un agent est dispatché alors qu'une réponse directe (sans
      subagent) suffirait — lister ces cas concrètement
- [ ] Réduire/resserrer les prompts de dispatch, en particulier
      `crew-new-task` et `crew-close-task` (les plus longs identifiés)
- [ ] Vérifier concrètement pourquoi la règle "Efficience de contexte"
      existante ne suffit pas (non lue par les subagents ? pas assez
      contraignante en pratique ? aucun mécanisme qui la fait respecter ?)
- [ ] Documenter dans `CLAUDE.md` si une règle plus stricte est nécessaire
      (ex. budget de tokens indicatif par dispatch, format de prompt de
      dispatch standardisé et court)
- [ ] Mesurer/comparer avant-après si possible (taille des prompts de
      dispatch, volume de contexte transmis) pour valider l'amélioration
- [ ] Évaluer un seuil de fenêtre de contexte plus bas pour les subagents
      (~100k au lieu de ~150k), différencié par rôle : agents
      d'implémentation (gros contexte code) prioritaires pour ce seuil
      serré ; personas read-only (`ceo`, `architect`, `manager` en mode
      lecture) déjà courtes, pas de gain à resserrer davantage. Attention
      au tradeoff : seuil trop bas → plus de cycles recap/relaunch →
      overhead qui peut annuler le gain token recherché

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

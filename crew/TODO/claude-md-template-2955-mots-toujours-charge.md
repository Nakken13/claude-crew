# Slimming `template/CLAUDE.md` + `CLAUDE.md` : 2955 → 1000-1200 mots (progressive disclosure)

Zone d'impact : `template/CLAUDE.md`, `CLAUDE.md` (racine, synchronisé), tous les
`skills/crew-*/SKILL.md` + miroirs `.claude/skills/crew-*/SKILL.md` (frontmatter +
corps), `scripts/dev/verify_plugin_package.py`, `skills/crew-update/SKILL.md` /
`scripts/crew_update.py` (migration des CLAUDE.md déjà personnalisés),
`crew/CLAUDE_CONTEXT/HISTORIQUE.md`.
Source : `crew/PROBLEMS/claude-md-template-2955-mots-toujours-charge.md` — audit § 4.A.
Arbitrage `architect` : rendu (pas de nouveau `RULES.md`, pas de `.claude/rules` +
`paths:`). **À faire EN DERNIER du batch** : dépend de ce que les tâches moniteur
(§ Reset de session) et continuité (`crew-start` étape 1) ajoutent au contexte.

## Description

`template/CLAUDE.md` pèse ~2955 mots (~4k tokens) injectés à chaque session de chaque
projet dérivé ; ~1300 mots doublonnent les skills `crew-start`/`crew-close-task`.
Cible 1000-1200 mots : garder une ligne par obligation, déplacer les procédures
détaillées vers les skills `crew-*` existants (chargés à l'invocation), raccourcir les
descriptions frontmatter (actuellement 336-600 chars) à ≤ ~40 mots.

## Actions

- [ ] Prérequis : les tâches `moniteur-contexte-seuil-fixe-stderr` et
      `continuite-session-sessionstart-precompact` sont closes (HISTORIQUE), et
      `CLAUDE.md` ≡ `template/CLAUDE.md` resynchronisés (`diff` vide) avant de couper.
- [ ] Mesure AVANT : `wc -w` des deux fichiers + somme des longueurs `description:`
      des 8 skills ; noter dans le fichier de tâche.
- [ ] Dispatcher `ceo` pour arbitrer la migration des CLAUDE.md déjà personnalisés
      dans les projets dérivés via `crew-update` (remplacement guidé vs diff manuel
      vs opt-in) ; transcrire la décision en actions dans `skills/crew-update/SKILL.md`
      (et `scripts/crew_update.py` si le mécanisme change).
- [ ] Rédiger la liste des obligations à conserver en une ligne chacune dans
      `template/CLAUDE.md` : schéma d'états + règle d'or ; « démarrer = `manager` /
      `crew-start`, jamais de déplacement de fichier nu » ; zones de batchs actifs
      disjointes ; clause personas 1 % ; routage skills une ligne par skill ; règle
      des 100 lignes ; seuils 150k/100k (formulation issue de la tâche moniteur) ;
      `crew/` ancré racine.
- [ ] Déplacer les procédures détaillées vers les skills correspondants (corps, pas
      frontmatter) : §0-4 du cycle de vie et PAUSED → `crew-new-task`/`crew-close-task`/
      `crew-start` ; anti-collision en 4 points + nettoyage automatique + description
      du hook → `crew-start`/`crew-status` ; commandes `/crew-*` → une ligne chacune.
      Aucune phrase d'ancrage d'obligation ne disparaît du CLAUDE.md (relire la liste
      ci-dessus en checklist).
- [ ] Frontmatter : réécrire `description:` des 8 skills `skills/crew-*/SKILL.md`
      à ≤ ~40 mots (déclencheur + effet), copier dans les miroirs `.claude/skills/`.
- [ ] Appliquer le résultat à l'identique dans `CLAUDE.md` racine (ou faire pointer
      la génération racine depuis le template si `crew-update` le prévoit) ;
      `python scripts/dev/verify_plugin_package.py` vert ; `check_placeholders.py` vert
      si des `<...>` ont été introduits.
- [ ] Mesure APRÈS : `wc -w` dans la cible 1000-1200, longueurs `description:` ;
      reporter avant/après dans HISTORIQUE.
- [ ] Passer `claude-md-management` sur `CLAUDE.md`/`template/CLAUDE.md` modifiés
      (audit qualité + learnings) avant de clore.

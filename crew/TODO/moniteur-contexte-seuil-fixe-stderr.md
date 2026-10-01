# Moniteur de contexte : `systemMessage` JSON, seuil scalé à la fenêtre, répétition par palier

Zone d'impact : `scripts/crew_hook.py` (`check_context_budget`, `_throttle_warnings`,
sortie JSON Stop), `crew/crew_hook.py` (copie synchronisée), `crew/test_crew_hook.py`,
`CLAUDE.md` + `template/CLAUDE.md` (§ Efficience de contexte / Reset de session),
`crew/CLAUDE_CONTEXT/HISTORIQUE.md` (entrée ré-arbitrant `alerte-contexte-150k`).
Source : `crew/PROBLEMS/moniteur-contexte-seuil-fixe-stderr.md` — audit § 4.D.
Arbitrage `architect` : rendu. Pas de détection de boucle (exigerait un PostToolUse
par appel, contraire à la tâche latence).

## Description

`check_context_budget` (hook Stop) alerte à 150k fixe, sur stderr, à chaque Stop une
fois le seuil franchi. Passer à une sortie `{"systemMessage": ...}` dans le JSON Stop,
scaler le seuil (fenêtre 1M → 800k ; détection : `model` du transcript contient
`[1m]` ou total observé > 210k), et ne répéter que tous les 50k tokens avec un état
par session.

## Actions

- [ ] TDD rouge : tests `check_context_budget` avec transcript factice —
      (a) fenêtre 200k, total 160k → alerte ; (b) `model` contenant `[1m]`, total
      160k → pas d'alerte, total 810k → alerte ; (c) total > 210k sans `[1m]` →
      fenêtre 1M inférée, seuil 800k ; (d) deux Stop successifs à 160k puis 180k →
      une seule alerte ; 160k puis 215k → deux alertes (palier 50k).
- [ ] TDD vert : seuil = 150k par défaut, 800k si fenêtre 1M détectée ; état de
      répétition par session (dernier palier alerté) stocké via `_throttle_warnings`
      ou dans l'entrée de session de `crew_lock.json` — réutiliser l'existant, pas
      de nouveau fichier d'état.
- [ ] Sortie : l'alerte quitte stderr et rejoint le JSON de décision Stop sous
      `"systemMessage"` (fusion avec les autres warnings déjà émis en JSON, ordre
      stable) ; vérifier dans un test que stderr ne contient plus le message.
- [ ] Mettre à jour `CLAUDE.md` et `template/CLAUDE.md` § Reset de session : la
      phrase « avertit automatiquement (stderr) » devient `systemMessage`, seuil
      150k (200k) / 800k (1M), répétition tous les 50k. Modifier les deux fichiers à
      l'identique (ils divergent déjà de ~24 mots : resynchroniser d'abord ou noter
      la divergence pour la tâche slimming).
- [ ] Synchroniser `crew/crew_hook.py` ↔ `scripts/crew_hook.py` ;
      `verify_plugin_package.py` et pytest verts.
- [ ] À la clôture : entrée HISTORIQUE qui ré-arbitre explicitement
      `alerte-contexte-150k` (2026-08-25) — ce qui change (canal, seuil, palier) et
      pourquoi (audit ECC).

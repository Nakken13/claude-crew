# Index TODO

Tâches pas commencées. Démarrer = déplacer le fichier vers `crew/CURRENT_TASKS/` (cf. `CLAUDE.md`).

- [Slimming `template/CLAUDE.md` + `CLAUDE.md` : 2955 → 1000-1200 mots (progressive disclosure)](claude-md-template-2955-mots-toujours-charge.md)
- [Continuité de session : hook `SessionStart` injectant un digest crew ≤ 2000 chars](continuite-session-sessionstart-precompact.md)
- [Fix `check_batches()` : ne parser que les lignes de liste (faux positif `CLAUDE.md`)](faux-positif-check-batches-claude-md.md)
- [Latence PreToolUse : pré-filtre shell + marqueur `.gate_armed` avant le spawn Python](latence-hook-pretooluse-spawn-python.md)
- [Moniteur de contexte : `systemMessage` JSON, seuil scalé à la fenêtre, répétition par palier](moniteur-contexte-seuil-fixe-stderr.md)

# alerte-contexte-150k

Validation du seuil de contexte 150k (`CLAUDE.md` § Reset de session) et de
son mécanisme technique côté session principale (`check_context_budget`,
`crew/crew_hook.py` / `scripts/crew_hook.py`).

## 🤖 / 🔍 Auto (IA)

- [ ] 🤖 `python -m pytest crew/test_crew_hook.py -q` — suite complète verte
      (22 tests dont 5 sur `check_context_budget` : pas de `transcript_path`,
      fichier absent, sous le seuil, au-dessus du seuil, dernière entrée
      assistant retenue même après un tour antérieur au-dessus du seuil).
- [ ] 🔍 `python scripts/dev/verify_plugin_package.py` — vérifier que
      `check_crew_hook_stays_in_sync` (nouveau) ne remonte aucun problème
      sur `crew/crew_hook.py` vs `scripts/crew_hook.py` (les deux copies
      doivent rester identiques hors la ligne `ROOT` connue).
- [ ] 🔍 Scénario bout-en-bout best-effort : construire un faux transcript
      JSONL (`{"message": {"role": "assistant", "usage": {"input_tokens":
      160000}}}` en dernière ligne) dans un fichier temporaire, invoquer
      `crew_hook.py` en simulant un payload Stop (`{"hook_event_name":
      "Stop", "transcript_path": "<chemin>", ...}` sur stdin) sur une copie
      de repo `crew/` jetable, et vérifier qu'un avertissement `[contexte]`
      apparaît sur stderr sans bloquer le tour (pas de `{"decision":
      "block"}` sur stdout dû à ce seul avertissement).
- [ ] 🔍 Vérifier que `CLAUDE.md` racine et `template/CLAUDE.md` ont bien la
      même formulation § Reset de session (seuil 150k + comportement
      subagent) — `diff` des deux sections doit être vide.

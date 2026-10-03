# moniteur-contexte-seuil-fixe-stderr

Validation de `check_context_budget` (`scripts/crew_hook.py` + copie `crew/crew_hook.py`) :
alerte `systemMessage`, seuil 150k / 800k, répétition par palier de 50k.

## 🤖 / 🔍 Auto (IA)

- [ ] 🔍 `diff scripts/crew_hook.py crew/crew_hook.py` vide ; `pytest crew/test_crew_hook.py -k context` vert.
- [ ] 🤖 Stop avec transcript factice 160k (fenêtre 200k) : stdout = JSON avec `systemMessage`
      contenant `[contexte]`, stderr sans `[contexte]` ; 2e Stop identique → pas de re-alerte.
- [ ] 🤖 Transcript `[1m]` : 160k muet, 810k alerte, 830k muet, 865k alerte ; total > 210k sans
      `[1m]` → seuil 800k.
- [ ] 🤖 Alerte + blocage simultanés : un seul JSON `{decision, reason, systemMessage}`.
- [ ] 🔍 `crew_lock.json` : `warned.context` = `{session_id: total}` ; entrée retirée au SessionEnd et
      quand le total repasse sous le seuil ; entrée d'une session concurrente conservée.

## 🖱️ Manuel (DEV)

Voir `crew/TESTS/DEV/moniteur-contexte-seuil-fixe-stderr.md`.

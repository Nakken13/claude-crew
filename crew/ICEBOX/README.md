Idées/tâches **parkées volontairement** — distinct de `TODO/` (qui veut dire
"pas encore commencée mais prévue"). Une tâche en ICEBOX n'est **pas** dans le
backlog actif : pas de deadline, pas de batch, pas d'attente à court terme.

Règles :
- Un fichier `.md` par idée parkée (même format qu'un fichier `TODO/` :
  description + actions en cases `- [ ]`).
- Une tâche part en ICEBOX depuis `TODO/` (décision explicite de dépriorisation)
  ou naît directement ici si l'idée n'est pas encore mûre.
- Pour la réactiver : déplacer le fichier vers `TODO/` (puis suivre le cycle
  de vie normal). Ne jamais démarrer une tâche directement depuis ICEBOX sans
  repasser par `TODO/` — sinon elle échappe au batching.
- Ne compte pas dans les vérifications de `CLAUDE_BATCH.md` (le hook
  `crew_hook.py` ne surveille que `TODO/`/`CURRENT_TASKS/`).
- `INDEX.md` est régénéré par `crew/crew_hook.py` — ne pas l'éditer à la main.

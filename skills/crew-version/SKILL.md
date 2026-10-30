---
name: crew-version
description: Affiche la version de crew-mates installée (vX.X.X). Trigger — "/crew-version", "quelle version de crew".
---

Lecture seule. Lancer :

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; PJ="${CLAUDE_PLUGIN_ROOT:-$ROOT}/.claude-plugin/plugin.json"
python -c "import json,sys; print('v'+json.load(open(sys.argv[1],encoding='utf-8'))['version'])" "$PJ"
```

Répondre avec la sortie seule (ex. `v0.3.1`), rien d'autre. Si le fichier est
introuvable (clone manuel sans plugin) : répondre `version inconnue`.

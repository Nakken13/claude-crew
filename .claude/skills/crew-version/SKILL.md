---
name: crew-version
description: Shows the installed crew-mates version (vX.X.X). Also triggers on — "/crew-version", "quelle version de crew", "which crew version".
---

Read-only. Run:

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; PJ="${CLAUDE_PLUGIN_ROOT:-$ROOT}/.claude-plugin/plugin.json"
python -c "import json,sys; print('v'+json.load(open(sys.argv[1],encoding='utf-8'))['version'])" "$PJ"
```

Answer with the output alone (e.g. `v0.3.1`), nothing else. If the file is not
found (manual clone without plugin): answer `unknown version`.

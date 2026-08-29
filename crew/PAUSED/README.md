Tâches **déjà démarrées** (`crew/CURRENT_TASKS/`) dont le code n'est pas fini
mais dont la suite dépend d'une action humaine (dev) que l'IA ne peut pas
exécuter seule : validation visuelle d'un rendu, test sur device réel,
confirmation d'une réponse de service externe, etc.

`git mv crew/CURRENT_TASKS/<slug>.md crew/PAUSED/<slug>.md` pendant le
blocage. Une fois la validation dev faite : `git mv` inverse vers
`crew/CURRENT_TASKS/<slug>.md`, le code reprend normalement.

Distinct de :
- `crew/ICEBOX/` — dépriorisation volontaire, aucun blocage technique, pas
  de tâche démarrée.
- `crew/TESTS/DEV/` — checklist de validation d'une tâche **déjà finie**
  (code 100 % coché, déjà historisée dans `HISTORIQUE.md`) ; ici le code
  n'est pas fini.

`INDEX.md` est régénéré par `crew/crew_hook.py` — ne pas l'éditer à la main.

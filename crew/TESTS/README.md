Checklists de validation des features finies, triées par exécutant :

- `IA/` — tests que l'IA peut dérouler seule (🤖 auto pytest/scénario/front,
  🔍 config/requête directe : curl, DB, logs, CLI).
- `DEV/` — tests qui nécessitent vraiment le dev (🖱️ manuel/visuel navigateur,
  mobile réel, ou item non outillé pour l'IA).

Même chantier → un fichier de chaque côté (mêmes nom + titre), seuls les
items diffèrent. `INDEX.md` (racine + par sous-dossier) est régénéré par
`crew/crew_hook.py` — ne pas l'éditer à la main.

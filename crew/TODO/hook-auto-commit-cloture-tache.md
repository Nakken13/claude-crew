# Hook Stop — commit git auto local à la clôture d'une tâche crew

Étendre `crew/crew_hook.py` (event Stop, déjà branché dans `.claude/settings.json`)
pour déclencher un commit git **local uniquement** (jamais de push) quand une
tâche crew vient d'être réellement clôturée — pas à chaque tour d'agent.

Contexte / pourquoi : incident réel sur ProjetA (projet issu de ce scaffold) —
un changement de config (port backend) a été committé et pushé sans revue
suffisante lors d'une session qui n'a jamais formellement clos sa tâche. Un
commit auto scopé à `crew/` et déclenché uniquement à la clôture réelle
(fichier disparu de `crew/CURRENT_TASKS/` + nouvelle entrée dans
`crew/CLAUDE_CONTEXT/HISTORIQUE.md`) donne une trace git systématique sans
pousser automatiquement — le push reste une décision humaine.

Ce repo (`organized` / claude-crew) est le scaffold source
(`~/.claude/templates/project-scaffold/`) : la modif doit vivre ici pour se
propager aux futurs `crew-init` / mises à jour sur tous les projets qui
l'utilisent (ProjetA, ProjetB, ProjetC, ProjetD, ProjetE,
ProjetF, etc.). Ne toucher à aucun fichier hors `crew/` (et
`.claude/settings.json` seulement si un nouvel event/matcher s'avère
nécessaire — a priori le Stop existant suffit, à confirmer en implémentant).

## Actions

- [ ] Détection de clôture : dans `crew_hook.py`, comparer l'état courant
      vs l'état précédent (le hook a déjà un mécanisme de snapshot d'état
      pour `CURRENT_TASKS`/`TODO`, cf. `prev.get("CURRENT_TASKS", [])` —
      s'appuyer dessus plutôt que réinventer) : une clôture = un slug
      présent dans `CURRENT_TASKS` au tour précédent et absent au tour
      courant, **et** une nouvelle entrée correspondante ajoutée dans
      `crew/CLAUDE_CONTEXT/HISTORIQUE.md` depuis le dernier commit auto (pas
      un flag manuel fragile — se baser sur le diff réel des fichiers).
- [ ] Extraire le(s) slug(s) de tâche(s) clôturée(s) à partir du nom de
      fichier disparu de `CURRENT_TASKS/` (ex. `hook-auto-commit-cloture-tache.md`
      → slug `hook-auto-commit-cloture-tache`), pour les réutiliser dans le
      message de commit.
- [ ] Scope du commit strictement limité aux fichiers sous `crew/` modifiés
      par la clôture : le fichier supprimé de `crew/CURRENT_TASKS/`, l'entrée
      ajoutée à `crew/CLAUDE_CONTEXT/HISTORIQUE.md`, les fichiers de test
      sortis dans `crew/TESTS/IA/` et/ou `crew/TESTS/DEV/`, et les
      `INDEX.md`/`CLAUDE_BATCH.md`/verrous batch régénérés par le hook lui-même
      dans la même passe. Utiliser des `git add <chemin>` explicites (liste de
      chemins connus/calculés), **jamais `git add -A` ni `git add .`** — ne
      jamais embarquer un fichier hors `crew/` même s'il apparaît modifié/staged
      par ailleurs dans le repo au moment du hook.
- [ ] Avant de commiter, vérifier qu'il y a bien un diff staged non vide sur
      le scope calculé (`git diff --cached --quiet` ou équivalent) — si rien
      à committer, ne rien faire (pas de commit vide).
- [ ] Message de commit généré automatiquement, référençant explicitement le
      ou les slugs de tâche(s) clôturée(s) (ex.
      `chore(crew): clôture tâche <slug>` ou équivalent), pour rester
      traçable et cohérent avec le style de message du repo (cf. commits
      existants pour convention).
- [ ] Gestion d'échec silencieuse et non bloquante : si le commit échoue
      (ex. un hook `pre-commit` du projet cible bloque, comme observé sur
      ProjetB avec un hook `no-float`), catcher l'erreur, logger un
      avertissement non bloquant (comme les autres warnings du hook, stderr /
      mécanisme existant) et **ne pas faire échouer la session** — le hook
      Stop ne doit jamais planter le tour à cause d'un commit git raté.
- [ ] Garde anti double-commit / idempotence : si le hook Stop se déclenche
      plusieurs fois sans nouvelle clôture entre-temps (ex. plusieurs Stop
      consécutifs dans une même session), ne rien committer une deuxième fois
      pour la même clôture déjà commitée — s'appuyer sur l'absence de diff
      staged (cf. action ci-dessus) plutôt que sur un flag séparé si possible,
      sinon documenter pourquoi un flag est nécessaire.
- [ ] Ne jamais exécuter `git push` — le commit reste strictement local,
      aucune tentative de push automatique, ni maintenant ni comme option
      cachée.
- [ ] Étendre `crew/test_crew_hook.py` (créer le fichier s'il n'existe pas
      encore — vérifier d'abord s'il existe un test existant pour
      `crew_hook.py` ailleurs dans le repo) avec au moins un scénario couvrant :
      clôture détectée → commit créé avec le bon scope de fichiers et un
      message référençant le slug ; deuxième appel du hook sans nouvelle
      clôture → aucun commit supplémentaire ; échec de commit (simuler un
      hook pre-commit qui rejette) → hook ne lève pas d'exception et le tour
      se termine normalement.
- [ ] Si le comportement visible pour l'utilisateur change (ex. le
      `statusMessage` du hook Stop dans `.claude/settings.json`, ou un
      nouveau comportement à documenter côté utilisateur), mettre à jour
      `crew/CLAUDE_CONTEXT/AGENTS.md` en conséquence — sinon laisser tel quel
      et le noter explicitement dans la review de fin de tâche.
- [ ] Vérifier si `.claude/settings.json` doit changer (nouveau matcher/event,
      timeout ajusté) — a priori l'event Stop existant suffit puisque la
      clôture (suppression `CURRENT_TASKS/` + entrée `HISTORIQUE.md`) se
      produit dans le même tour que les autres actions crew déjà gérées par
      ce hook ; ne modifier ce fichier que si l'implémentation le justifie
      réellement.

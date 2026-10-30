# Vérifier en réel le mod file-lock-monitor

**Batch** : Vérification réelle des mods hooks. Dépend de `verif-mod-batch-eta-cost.md` (séquence du batch).

**Description** : Surveille les écritures de fichiers (`tool.call` Edit/Write/MultiEdit) : conflit avec zone/verrous d'une autre session (`crew_lock.json`, `Zone :`), alertes et bandeau `locks` ; TTL des touches 15 min.

Surface : bandeau `locks` / alerte. Événements : tool.call.
Fichiers : `hooks/mods/file-lock-monitor.ts`, dépendance commune `hooks/mods/shared.ts` (helpers, `crewRuntimeState`, `crewUiState`), tests `hooks/mods.test.ts`.

## Actions

- [ ] Lancer les tests unitaires (`claude plugin test .` depuis la racine, cf. README) et noter le résultat du bloc de ce mod.
- [ ] Charger le mod dans une vraie session Claude Code (plugin chargé via `hooks/register.ts`) : vérifier l'enregistrement sans erreur dans les logs.
- [ ] Édition d'un fichier hors de toute zone verrouillée : aucune alerte.
- [ ] Avec une 2e session simulée dans `crew_lock.json` verrouillant une zone, éditer un fichier de cette zone et constater l'alerte/bandeau de conflit.
- [ ] Vérifier l'extraction du chemin (`file_path`, `filePath`, `path`) et la normalisation worktree/relatif/absolu (séparateurs Windows).
- [ ] Vérifier l'expiration des verrous (TTL) : entrée plus vieille que le TTL ignorée.
- [ ] Cas limite : `crew_lock.json` absent/corrompu, outil non écrivant (Read/Bash) ignoré, event sans chemin : passe sans erreur.
- [ ] Si une anomalie est trouvée : la consigner dans `crew/PROBLEMS/` (pas de correctif dans cette tâche).
- [ ] Relancer `claude plugin test .` après toute correction liée et confirmer le vert.

## Critère de réussite

Conflit signalé uniquement pour une vraie collision de zone avec une autre session ; aucun faux positif sur sa propre session. Tests unitaires verts.

## Commande de test

`claude plugin test .` (suite `hooks/mods.test.ts`), puis vérification manuelle en session réelle.

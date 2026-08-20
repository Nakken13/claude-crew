# AGENTS.md — <NOM_PROJET>

Guide invariants + repo map pour tout agent (Claude Code ou autre) travaillant
sur ce projet. À remplir/vérifier avant le premier vrai chantier — ne pas
laisser de placeholder `<...>` non résolu.

## Stack

<Lister la stack réellement vérifiée depuis les fichiers de manifeste
(package.json, requirements.txt, go.mod, Cargo.toml...), pas de suppositions.>

## Repository map

```text
<arborescence des dossiers significatifs, avec un rôle en une ligne chacun>
```

## Commandes vérifiées

```bash
<install>
<dev/run local>
<tests>
<build>
```

Toute commande listée ici doit avoir été exécutée avec succès au moins une
fois — ne pas documenter une commande non testée.

## Règles de code

<Conventions spécifiques au projet : structure des routes/handlers, schémas
de validation, style de logging, ce qui ne doit jamais être fait (ex. pas de
print debug, pas de secret loggé, pas de migration destructive sans accord).>

## Secrets and boundaries

<Où vivent les secrets (env vars, vault...), ce qui ne doit jamais atteindre
le client/logs, référence vers SECURITY.md si présent.>

## Documentation routing

- Vision produit / scope : `PRODUCT.md` (si présent).
- Conventions de contribution : `CONTRIBUTING.md` (si présent).
- Limites sécurité : `SECURITY.md` (si présent).
- Guide global de contexte : `crew/CLAUDE_CONTEXT/AGENTS.md`.

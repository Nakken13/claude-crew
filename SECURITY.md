# SECURITY.md — <NOM_PROJET>

À remplir dès que le projet a de l'auth, des secrets, ou des données
utilisateur sensibles ; à supprimer sinon.

## Secrets

<Où ils vivent (env vars, vault manager...), jamais commit `.env`, jamais
loggés, jamais renvoyés au client.>

## Auth boundaries

<Modèle d'auth (tokens, sessions, RLS...), où vit le token côté client (ex.
en mémoire seulement, jamais localStorage si XSS est une préoccupation),
comment le refresh est géré.>

## Données sensibles / PII

<Quelles données sont sensibles dans ce projet, règles de masquage/logging,
rétention.>

## Pré-production checklist

<Ce qui doit être vérifié avant un premier déploiement public : `/docs`
désactivé, checkpointer/dev fallback qui ne doit jamais tourner en prod,
CORS, rate limiting...>

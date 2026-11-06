# SECURITY.md — <NOM_PROJET>

Fill in as soon as the project has auth, secrets, or sensitive user data;
delete otherwise.

## Secrets

<Where they live (env vars, vault manager...), never commit `.env`, never
logged, never sent back to the client.>

## Auth boundaries

<Auth model (tokens, sessions, RLS...), where the token lives client-side (e.g.
in memory only, never localStorage if XSS is a concern), how refresh is
handled.>

## Sensitive data / PII

<Which data is sensitive in this project, masking/logging rules,
retention.>

## Pre-production checklist

<What must be verified before a first public deployment: `/docs`
disabled, checkpointer/dev fallback that must never run in prod,
CORS, rate limiting...>

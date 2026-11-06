# Project crew configuration

File owned by the project: `/crew-update` never modifies it. Lines
`key : value`, freely editable.

## Remote claims (several devs on the same repo)

Syncs in near real time "who is working on what" and the `TODO/` tasks
created, via the git ref `refs/crew/claims` (pushed on its own, never on `main`).
Enable it when several people run `/crew-start` on the same repo;
each one must enable it to be protected. Details: `crew/CLAUDE_CONTEXT/AGENTS.md`.

remote_claims : false

Git remote used for the ref (default: `origin`):

claims_remote : origin

Ref carrying the claims (default: `refs/crew/claims`). If your git server refuses
custom refs, uncomment to fall back to a dedicated branch:

# claims_ref : refs/heads/crew-claims

# Global guide — product invariants + anti-patterns

Extended context guide, read only when a cross-stack rule is ambiguous
(otherwise reading the `AGENTS.md` of the relevant subtree is enough). Fill
in over the life of the project with invariants written nowhere else:
product decisions that cannot be deduced from the code, pitfalls already
hit, anti-patterns not to reintroduce.

## Auto-commit when a crew task is closed

Closing a crew task (file gone from `crew/CURRENT_TASKS/` + new entry in
`crew/CLAUDE_CONTEXT/HISTORY.md` in the same turn) triggers a **local-only**
git commit, scoped to `crew/` (see `auto_commit_closure` in
`crew/crew_hook.py`, Stop event). The `git push` is **never** automatic — it
always stays an explicit human decision. Source incident: a change outside
`crew/` had been committed and pushed without review during a session that
never formally closed its task; this auto-commit gives a systematic git trace
of every closure without pushing anything on the user's behalf.

## Pitfall: synchronized copies (plugin source repo)
- Editing the root `CLAUDE.md` → copy it identically to `template/CLAUDE.md` **and** `~/.claude/templates/project-scaffold/`; check with `python scripts/dev/verify_plugin_package.py`.
- Duplicated engine: `crew/crew_hook.py` ↔ `scripts/crew_hook.py` (only the `ROOT =` line differs), `crew/crew_update.py` ↔ `scripts/crew_update.py`, `.claude/{skills,agents}` ↔ `{skills,agents}/`: every edit goes in both.
- Tests: `python -m pytest crew/` and `claude plugin test .` (`npx vitest` alone fails: `claude-code/testing` not found).
- `crew/` tracking data (TODO, CURRENT_TASKS, PAUSED, PROBLEMS, ICEBOX, TESTS, CLAUDE_BATCH.md, HISTORY.md) is gitignored: never in a worktree, work in the main checkout.

## Team mode — `/crew-collab` (solo by default)

A solo project needs no remote ref, no claims and no 👤 in the status bar. `/crew-collab on`
(`crew_hook.py collab on --name <name>`) asks for your name, turns on `remote_claims` and saves `collab_name` in
`crew/CLAUDE_CONTEXT/CREW_CONFIG.md`: that name owns all your claims. `/crew-collab off` returns everything to the
base form (claims off, name removed, ignore list deleted; claims already published stay on the remote).
`/crew-collab status` shows who has how many tasks (`Bob 12 | Alice 5 | you 1`).

`TODO` tasks already owned by other devs (brought in by a pull, without them using crew): `ignore snapshot` assigns
each `TODO` to its owner without asking whenever it is already indicated — a mention in the file (`Owner: <name>`,
`Assigned to: <name>`, `Claimed by: <name>` or `Responsible: <name>`, French aliases `Assigné à` / `Responsable`,
first 40 lines) or a published remote claim; tasks under your own name stay startable. `TODO` tasks with no mention at
all are set aside anyway (filed as "unassigned", listed in `unmarked`): never run, no question asked;
`ignore snapshot --owner <name>` gives them an owner. The result lives in `crew/CLAUDE_CONTEXT/crew_ignored.json`
(local, untracked, nothing is published): `next-task` skips these tasks ("ignored locally (task of <name>)"), `TODO`
tasks added afterwards stay startable, they remain visible in `/crew-status` and the dashboard, and the status bar
shows `👤N` (only while team mode is on). Other subcommands: `ignore add <slug> [--owner <name>]` ·
`ignore remove <slug>` · `ignore list` · `ignore off`.

## Remote claims (several devs on the same repo)

Opt-in: `remote_claims : true` in `crew/CLAUDE_CONTEXT/CREW_CONFIG.md` (default
`false`; each dev enables it to be protected, `claims_remote` changes the remote,
`origin` by default; `claims_ref : refs/heads/crew-claims` = fall back to a branch if
the server refuses custom refs). The `crew/` folders remain the truth for task state;
the git ref `refs/crew/claims` (pushed on its own, never on `main`) adds "who is doing
what" + the published `TODO` tasks: a `claims.json` slug → `{status, owner,
author, batch, zone, branch, ts, title, body}`.

Commands (`python crew_hook.py claims …`, run by `/crew-start`,
`/crew-new-task`, `/crew-close-task`): `fetch` · `claim <slug> --session --batch
--branch --zone` · `release <slug> [--done]` · `publish <slug> --title --zone
--body-file` · `check-dup --title --zone` · `materialize <slug>` · `list`.
`next-task` merges the remote claims (reason `remote claim: <owner>` — the
string is emitted by the code, hence still French; it means "remote claim: <owner>");
the dashboard shows them as a read-only Kanban; the session digest lists
the open tasks (no network).

**Guaranteed** (online devs who use the sync): atomic claim
(`push --force-with-lease` on the tip read, 3 attempts), never two claims with
overlapping zones, no other dev's entry silently overwritten.

**Limits**: only devs with `remote_claims` are protected (the Stop hook
warns if the ref exists without the flag); a semantic duplicate (very
different title and zone) cannot be detected by script — Claude judges the list of titles;
stale claim for up to 8 h if a crash happens without `release` (TTL computed from `ts`, approximate
if clocks drift); push permission on the remote required; offline = soft mode
(warning, claim not published); does not protect against code merge
conflicts.

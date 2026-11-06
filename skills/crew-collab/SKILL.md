---
name: crew-collab
description: Turns the project's team mode on or off — asks for your name, enables remote claims (your tasks are claimed under your name, git ref pushed on its own), assigns TODO tasks that other devs already own, and shows who has how many tasks. Without this mode the project stays solo, with no sync and no 👤 in the status bar. Trigger — "/crew-collab", "collab mode", "we are several people on this project".
---

"Project is a team" switch. **The project is solo by default**: no remote
branch, no claims, plain status bar (no 👤). This skill is the only documented
way to turn on multi-dev sync (`remote_claims`). The work itself is done by the
deterministic `crew_hook.py collab` / `ignore` commands; this skill asks the
questions and presents the result.

**Repo-root anchoring is mandatory**: every `crew/...` path is resolved from the
repo root (`git rev-parse --show-toplevel`), never from the cwd.

Common preamble for every command (plugin: the plugin's `scripts/crew_hook.py`;
manual clone: `crew/crew_hook.py`):

```bash
ROOT="$(git rev-parse --show-toplevel)"; HOOK="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/scripts}"; HOOK="${HOOK:-$ROOT/crew}/crew_hook.py"
CLAUDE_PROJECT_DIR="$ROOT" python "$HOOK" collab status
```

JSON output of `collab status`: `collab` (bool), `name` (your name), `ignored`
(number of TODO tasks set aside), `people` = `[{name, tasks, me}]` sorted by task
count (TODO tasks assigned to others, other devs' remote claims, and your own
current tasks). Slash argument: `on`, `off`, `status`; with no argument, read
`status` first, then suggest the sensible action (inactive → `on`; active →
`status` + `off` / change name).

## `status`

One line for the mode and your name, then **one person per segment, separated by
` | `**: `Bob 12 tasks | Alice 5 tasks | Sofian (you) 1 task`. Add `(you)` when
`me` is true; use the singular for 1. A name of `(unassigned)` means TODO tasks
set aside with no known owner. Nothing else.

## `on`

1. **Ask for your name** (free-text message, not `AskUserQuestion`: it is text).
   Suggest `git config user.name` as the default. This name becomes the owner of
   **all your claims**: it is what other devs will see. Allowed characters:
   letters, digits, space, `.` `@` `-` `_` (60 max); the script rejects anything
   else — ask again without insisting. Two devs must not pick the same name.
2. Run `collab on --name "<name>"`. If the output contains `warning` (git remote
   not found), repeat it as is: claims will work in soft mode (nothing is
   published) until a remote exists.
3. **Assign the TODO tasks already present, without asking anything**: run
   `ignore snapshot`. It reads each TODO's owner by itself: a mention written in
   the file (`Owner: <name>`, `Assigned to: <name>`, `Claimed by: <name>` or
   `Responsible: <name>`; French aliases `Assigné à` / `Responsable` work too) or
   an already published remote claim. Tasks under **your** name stay startable;
   every other task is kept away from `/crew-start`. Tasks with **no mention at
   all** (`unmarked` in the output) are set aside anyway, filed as "unassigned":
   they are there but do not belong to you, so they are never run. Do not ask
   anything. If `unmarked` is not empty, say so in one sentence and mention that
   `ignore snapshot --owner "<name>"` gives them an owner if you know it (it only
   touches the unassigned ones).
   TODO tasks added later are not affected (run `ignore snapshot` again after a
   pull that brings some in).
4. Summarise in 3 lines: the name saved; what was assigned (per person, `status`
   format); `/crew-start`, `/crew-new-task` and `/crew-close-task` now claim and
   publish under your name (ref `refs/crew/claims`, never on `main`, push access
   required) and the bar shows `👤N`; `/crew-collab off` goes back to solo.
   `on` itself pushes nothing.

## `off`

Confirm via `AskUserQuestion` ("Go back to solo? Turns remote claims off, removes
your name, deletes the list of tasks set aside and the 👤 from the status bar.
Claims already published on the remote are not deleted.") then run `collab off`.
Tasks and the `crew/` folders are not touched.

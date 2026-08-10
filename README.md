# organized

**File-based task lifecycle + multi-agent collision prevention for Claude Code.**

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](./LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#whats-in-the-box)
[![Built for Claude Code](https://img.shields.io/badge/built%20for-Claude%20Code-5A45FF.svg)](https://github.com/anthropics/claude-code)
[![GitHub stars](https://img.shields.io/github/stars/Nakken13/organized?style=social)](https://github.com/Nakken13/organized)

Claude Code forgets everything between sessions. Run two instances on the
same repo and they'll happily edit the same files at the same time, with no
warning. `organized` fixes both — with markdown files and two stdlib-only
Python hooks, no server, no DB, no dashboard.

Install in one command, working in five minutes, nothing to host.

**[Quick start](#quick-start)** · **[How it works](#how-it-works)** ·
**[Batching](#the-actual-differentiator-batching)** ·
**[What's in the box](#whats-in-the-box)** · **[Is this for you?](#not-for-you-if)**

## The problem

- **Session amnesia.** Every new Claude Code session starts blind: what's
  done, what's half-done, why a decision was made — gone unless you paste it
  back in yourself.
- **Multi-agent collisions.** Parallelizing Claude Code (one instance per
  workstream) is the obvious way to go faster. It's also the fastest way to
  get two agents editing the same file at the same time, silently.

## How it works

A task is a file. Its state *is* which folder it's in — no status field to
forget to update, `git mv` is the state transition:

```
organized/PROBLEMS/<slug>.md        raw bug/friction report
organized/TODO/<slug>.md            not started
organized/CURRENT_TASKS/<slug>.md   in progress (moved here when work starts)
organized/CLAUDE_CONTEXT/HISTORIQUE.md   done — what, when, key files/commits (long-term memory)
organized/TESTS/IA/ + /DEV/         validation checklist, split by who can run it (agent vs human)
```

A file is never in two folders at once. `git log --follow` on a task file is
its entire history.

## The actual differentiator: batching

Plenty of scaffolds give you a prompt template and a folder layout. What
`organized` adds is tracking *which files each task touches* (its "zone"),
grouping tasks that share a zone into the same batch, and flagging it —
before a task moves to `CURRENT_TASKS` — if its zone overlaps an **active**
batch it doesn't belong to. A routing rule tells Claude Code to check this
before starting any task, backed by a hook that re-checks and warns
(non-blocking, stderr) on every turn. You catch the collision before you
point a second Claude Code instance at the same code, not after you've
resolved the merge conflict.

```
Batch A — Zone: frontend/checkout/**        [1 task in CURRENT_TASKS]
Batch B — Zone: backend/payments/**         [1 task in CURRENT_TASKS]
Batch C — Zone: frontend/checkout/**  <-- overlaps Batch A, flagged before start
```

This is the part that matters once you're running more than one agent — the
folder lifecycle alone is a nice-to-have, the collision check is what keeps
parallel Claude Code instances from stepping on each other.

## What's in the box

| Piece | What it does |
|---|---|
| `organized/` | The task lifecycle folders (`PROBLEMS`/`TODO`/`CURRENT_TASKS`/`TESTS`/`CLAUDE_CONTEXT`/`ICEBOX`) |
| `organized_hook.py` | Runs on `Stop` — regenerates `INDEX.md` files, warns (non-blocking, stderr) on zone overlaps and orphaned tasks |
| `spec_to_task_hook.py` | Runs on file writes — keeps specs and tasks in sync |
| `/organized-init` | Bootstraps the whole scaffold onto a project, resolves every `<placeholder>`, fails loud if one is left unresolved |
| `/organized-new-task`, `/organized-close-task`, `/organized-status` | Run the lifecycle + batching instead of doing it by hand every time |
| `.claude/agents/ceo.md` `manager.md` `comms.md` `architect.md` | Subagent personas routed by decision type — business/priority calls, task breakdown, user-facing copy, and structural tech choices don't get answered by the same voice that writes your diff |
| `CLAUDE.md` / `AGENTS.md` | Skill routing + context-efficiency rules (no reading 2000-line files whole) wired into Claude Code from day one |

Everything is plain markdown + JSON state — readable, greppable, diffable in
a normal PR review. No hosted board, no account, nothing to sync.

## Quick start

```bash
git clone https://github.com/Nakken13/organized.git
cp -r organized/{CLAUDE.md,AGENTS.md,PRODUCT.md,CONTRIBUTING.md,SECURITY.md,organized,.claude} your-project/
```

Open `your-project` in Claude Code and run:

```
/organized-init
```

That's it — this detects your stack, resolves every `<placeholder>` with the
real repo info, and fails loud (`check_placeholders.py`) until nothing is
left unfilled. Full step-by-step in [`CLAUDE.md`](./CLAUDE.md).

Once it's running, three commands drive day-to-day work:

- `/organized-new-task` — create a task, auto-categorized into a batch
- `/organized-close-task` — close a finished task: checks, history, tests moved out
- `/organized-status` — read-only report: active batches, overlaps, orphaned tasks

## Not for you if

- You're solo, one Claude Code session, small script — this is overhead you
  don't need yet.
- You want a hosted task board with a UI — this is deliberately local-first,
  files-only, no service to run.

## Contributing

Issues and PRs welcome — see [`CONTRIBUTING.md`](./CONTRIBUTING.md). If
`organized` saves you a merge conflict, a star helps other people find it.

## License

MIT — see [`LICENSE`](./LICENSE).

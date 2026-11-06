# Task lifecycle, batching and context efficiency

Doc read **on demand** (moved as-is out of `CLAUDE.md`, which keeps only the routing). Read it before creating/moving a task, touching `CLAUDE_BATCH.md`, or when in doubt about the context thresholds.

## Task management — single lifecycle (folder model)

A task = one `.md` file that **moves** (`git mv`); never in two folders.

```
Raw problem → crew/PROBLEMS/   Not started → crew/TODO/   Parked → crew/ICEBOX/
Started → crew/CURRENT_TASKS/  Blocked (dev) → crew/PAUSED/
Code done → crew/CLAUDE_CONTEXT/HISTORIQUE.md + crew/TESTS/{IA,DEV}/<workstream>.md (task file deleted)
Validated → boxes checked; a fully checked IA test → crew/CLAUDE_CONTEXT/TESTS_DONE/
```

Single source = `crew/` folders (a root `TODO.md`/`PROBLEMS.md` is only a pointer).

### 0-1. `PROBLEMS/` (inbox: one file per bug/friction, `🔴`/`🟡`/`✅`) → `TODO/` (backlog: never started, actions as `- [ ]`, categorized in `crew/CLAUDE_BATCH.md` when added)

### 2. Start → move to `CURRENT_TASKS/`
Anti-collision is mandatory before any move (`/crew-start`, see § Batching). Keep the boxes up to date. `ICEBOX/`: never started directly, go back through `TODO/`.

### 2bis. `PAUSED/` — blocked awaiting dev validation
A task already started whose continuation depends on a human action (visual rendering, real device, external answer): `git mv` to `PAUSED/`, back to `CURRENT_TASKS/` once validated. Counts as active for anti-collision. Never resumed automatically by the AI.

### 3. Code done
Delete the file from `CURRENT_TASKS/`, record it in `HISTORIQUE.md`, produce the tests **if the test policy asks for it** (`/crew-close-task`). **Do not check** the tests at this stage.

### 4. `TESTS/` — IA / DEV checklists
**Policy**: `crew/CLAUDE_CONTEXT/TESTS_POLICY.md` decides whether a checklist is written. Absent (project not yet migrated) → historical behavior (`full`) until `/crew-update`.
`IA/`: the AI runs them alone (pytest, `playwright`, curl, DB, logs); `DEV/`: real human action (real mobile, visual judgment). Same workstream = one file on each side; main path + edge cases.

**Golden rule:** not started → `TODO/`; started → `CURRENT_TASKS/`; blocked on dev validation → `PAUSED/`; done → `HISTORIQUE.md` + `TESTS/`.

## Batching — parallelization (`crew/CLAUDE_BATCH.md`)

**One batch = one Claude**; several batches run in parallel. Every new task is also added to `CLAUDE_BATCH.md`: known impact zone → existing batch if overlap/dependency, otherwise new batch (`Zone :` line, i.e. the impact zone); unknown zone → the « À classer » section ("to be classified"). Task done → strike its line (`~~`slug.md`~~`), never delete it; a fully struck batch is removed automatically by the hook.

**Invariant: the zones of two active batches (≥1 task in `CURRENT_TASKS/` or `PAUSED/`) are disjoint**; shared files → same batch.

### Anti-collision check before starting a task
`crew_hook.py next-task` (run by `/crew-start`) does it deterministically: locks of other sessions, active batches (`CURRENT_TASKS/`, `PAUSED/`), overlap of `Zone :` → candidate discarded, next one tried; nothing startable → report to the user. Manual start outside `/crew-start`: apply the same rules by hand. The Stop hook warns (non-blocking) about missed overlaps; `/crew-status` for an on-demand view.

## Context efficiency

### File reads
**Never read a file of more than 100 lines in full** without bounding the area with grep (especially `HISTORIQUE.md`, `graph.json`, lockfiles, migrations). Never the full output of a long command: only errors/warnings.

### Session reset
- Threshold ~**150k tokens** (main session): beyond it, **recommend `/clear` or a new session**. The Stop hook warns (`systemMessage`; same 150k threshold whatever the window (200k or 1M), repeated every 50k) but the rule applies as soon as the conversation looks large.
- Session near the limit, task unfinished: commit, note the state in `HISTORIQUE`/`CURRENT_TASKS`, suggest restarting.
- **Subagents**: ~100k for implementation (without dropping below ~80k); ~150k for read-only personas. Self-imposed textual instruction: beyond it, stop, produce a **recap** (work done, state, files, blockers) and relaunch an agent with that recap.

### Segmented AGENTS.md guides
Global guide `crew/CLAUDE_CONTEXT/AGENTS.md`; one `AGENTS.md` per significant subtree (read it alone in a single-subtree session). **`crew/` stays unique at the repo root** even if the cwd is a subfolder: resolve the root (`git rev-parse --show-toplevel`) before any `crew/...` write, otherwise a phantom `crew/` is created.


## Personas — detailed routing (moved from CLAUDE.md)

Roles/points of view (`Agent({subagent_type: "<name>"})`), not technical procedures. Dispatch a persona when the decision has ≥2 real options in its domain, or when the user asks for it; not for a question whose answer is obvious or already settled (each dispatch opens a full subagent). Threshold per persona: `legal` and `architect` strict (new trigger or a choice that commits what follows → dispatch, and also when in real doubt about whether it is "obvious"); `designer`, `ceo`, `comms`, `social`, `seo` at judgment (≥2 real options).

- Business arbitration/prioritization/scope, "is it worth it?" → `ceo` (read-only).
- Breakdown into tasks, batches, sequencing → `manager` (writes under `crew/`).
- **Starting an existing task** (`TODO/` → `CURRENT_TASKS/`) → `/crew-start` (its `next-task` script does the zone anti-collision, no persona); `manager` only to classify a task without a batch. Never a bare file move.
- Marketing/landing/email copy, brand tone → `comms` (check `AGENTS.md` for the tone of a product agent).
- Structuring technical choice (2+ approaches, refactor now or later) → `architect` (read-only).
- UX/UI decision (flows, hierarchy, retention, quantified specs, platform conventions) → `designer` (read-only; touching up a screen → `impeccable`).
- New legal exposure (personal data, third-party SDK, payment, minors, AI, user content, scraping, licence, regulated sector, new country, influencer/contest/prospecting/comparative claims) → `legal` (read-only) before coding.
- Organic distribution on social networks (platform/format, cadence, hooks, why a video plateaus, test plan) → `social` (read-only; hands a brief to `comms`).
- Search visibility (Google, stores, AI answers: indexing, keywords, schema.org, Core Web Vitals, ASO) → `seo` (read-only; hands a brief to `comms`) — without a public web surface or store listing, do not invoke it; social networks → `social`.

Personas never implement; doubt between two → the one closest to the core of the request.

**Persona duplicate**: `agents/` (source of the crew-mates plugin, served via `${CLAUDE_PLUGIN_ROOT}`) and `.claude/agents/` (copy for bootstrapped projects in manual clone mode) have the same content; a project uses only one of them. In this repo (which is the source) both coexist by construction; never install the plugin **and** keep `.claude/agents/` in a client project (the personas would appear twice).

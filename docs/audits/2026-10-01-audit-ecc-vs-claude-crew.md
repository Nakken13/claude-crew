# Audit — claude-crew vs ECC 2.2.0 plugin (tokens & responsiveness)

Date: 2026-10-01. Goal: identify what ECC does to consume less context /
respond faster, and what claude-crew needs to complement.
Measurements taken on this repo (Windows 11, Python 3.12, Node). The problems
found are recorded in `crew/PROBLEMS/` (one file per problem),
and the trade-offs come from the `architect` persona.

## 1. Orders of magnitude

| | claude-crew | ECC 2.2.0 |
|---|---|---|
| Agents / skills / commands | 4 (6 on origin/main) / 8 / 0 | 68 / 286 / 94 |
| CLAUDE.md loaded every session | `template/CLAUDE.md` 2955 words (~4k tokens) | ~600 words (3.9 KB) |
| Frontmatter descriptions (always loaded) | ~3.4k chars skills + ~1.5k agents | ~80k chars skills + ~10k commands |
| Hook entries | 4 (PreToolUse, PostToolUse Write, Stop, SessionEnd) | 23, consolidated into dispatchers, sync/async split |
| Hook profile / disabling | none | `userConfig.hook_profile` minimal/standard/strict + `ECC_DISABLED_HOOKS` |
| Session continuity | none (crew-start rereads `crew/` by hand) | SessionStart digest capped at 8000 chars + PreCompact Haiku summary |
| Context monitor | fixed 150k threshold, stderr | window-scaled threshold, 60k repeat, debounced `additionalContext` |

ECC is not a model of frugality in itself: its skills listing costs
~20k tokens per session, GateGuard refuses the first Edit/Bash per file
(one extra round trip each time, observed in this session),
and `observe` is registered twice. What we should borrow from it are
**mechanisms**, not its volume.

## 2. claude-crew measurements

- PreToolUse hook (`Bash|Edit|Write|MultiEdit`): 540-1200 ms per tool
  call. Bare Python startup: 500-1000 ms; `python -I -S` ~800 ms; bare
  Node 380-740 ms. **The cost is process spawning, not the language** —
  migrating to Node would bring nothing here.
- Stop hook: ~740 ms. Must stay synchronous (can return
  `{"decision":"block"}`).
- False positive reproduced on this repo: `check_batches()` reads `` `CLAUDE.md` ``
  in the header prose of `crew/CLAUDE_BATCH.md` and emits
  "references a nonexistent task: `CLAUDE.md`" — in **all**
  bootstrapped projects (the header comes from the template).
- `template/CLAUDE.md`: skills routing 697 words, lifecycle 910,
  efficiency 457, personas 405, batching 396, commands 248, graphify 143.
  The `crew-start` and `crew-close-task` skills already re-encode
  the anti-collision and closure procedure: ~1300 words are read twice
  on every invocation.
- Repo drift: the local copy is **behind `origin/main`** (`designer` and
  `legal` personas merged via PR, present in the installed 0.2.1 plugin)
  and **ahead** by one commit (`89e83da`). Resync before any
  work.

## 3. What ECC does that we can adopt

Reusable as is (adapted to Python):
1. **Hook gating** by profile + list of disableable ids, exposed as
   `userConfig` in `plugin.json` and as an environment variable.
2. **SessionStart with a hard cap** (chars) and an `off` switch — bounds
   the fixed cost paid every session.
3. **Compaction threshold read from the transcript's `usage`**, scaled to the window
   (160k/200k, 250k/1M), with a repeat interval.
4. **Sync/async split**: any hook that does not return a blocking decision
   goes `"async": true` (for us: SessionEnd, PostToolUse Write).
5. **Accumulate, then act once at Stop** rather than on every edit
   (ECC: format/typecheck; for us: already the case for the index/journal,
   to be kept).
6. **`context-budget` audit skill** (prompt-only): descriptions > 30 words,
   skills > 400 lines, combined CLAUDE.md > 300 lines, ~500 tokens per
   MCP tool → to be offered as a `/crew-status --context` pass or in
   `claude-md-management`.

Not to adopt: GateGuard fact-forcing (friction, +1 turn per file),
Haiku LLM summary in PreCompact (synchronous latency, CLI dependency, store
outside `crew/`), observe/instincts (heavy, Windows no-op), Node dispatcher
(no gain: our 4 hooks are already a single script).

## 4. Trade-offs (`architect` persona)

**A. Slimming `template/CLAUDE.md`** → progressive disclosure, target
1000-1200 words. Keep each obligation in one line (state diagram + golden
rule, "start = manager / crew-start, never a bare git mv",
disjoint-zones invariant, 1% personas clause, skills routing 1 line
per skill, 100-line rule, 150k/100k, `crew/` anchored at root).
Move the detailed procedures (§0-4, PAUSED, 4-point anti-collision,
auto-cleanup, hook description) into the existing `crew-*` skills —
no new `RULES.md`. Rule out `.claude/rules` + `paths:`
(rules that are not path-scoped). Risk: non-adherence if an obligation loses
its anchor sentence; migration of already-customized CLAUDE.md files
(`crew-update`) to be arbitrated with `ceo`. Effort M.

**B. PreToolUse latency** → shell pre-filter + file marker.
`save_locks` writes/removes `crew/CLAUDE_CONTEXT/.gate_armed` when
≥ 2 sessions; the hook command does `[ -e …/.gate_armed ] || exit 0`
before spawning Python (for `Bash`, always let through the `git mv` /
`crew-resume:` claims that must write the lock even when solo).
Spawn avoided in the majority case (one session): gain ≈ 0.4-1 s per
tool call. `CREW_HOOK_PROFILE=minimal` as an escape hatch. Effort S/M.

**C. Session continuity** → SessionStart hook (`startup|resume|compact`)
injecting a pure-file digest ≤ 2k chars via `additionalContext`:
CURRENT_TASKS/PAUSED (slug, title, boxes), active batches + zones, other
sessions' locks, last 3 HISTORIQUE titles, batch warnings. Derived view,
never rewritten into `crew/` (single source respected). Replaces
the 3-6k tokens of tools that `crew-start` spends rereading the state. Rule out
PreCompact (redundant: `SessionStart` source `compact` re-injects the
digest). Effort S/M.

**D. Context monitor** → re-arbitrate `alerte-contexte-150k`
(2026-08-25): move from stderr to `{"systemMessage": …}` in the Stop
JSON, scaled threshold (1M window detected via `model` `[1m]` or total
> 210k → 800k), repeat every 50k with per-session state. Rule out
the "5 identical tools" detection (it would require a PostToolUse per call,
contrary to B). Effort S.

## 5. Recommended implementation order

1. Resync the repo (`git pull --rebase origin main`).
2. `check_batches` bug: parse with `TASK_LINE_RE` (already used by
   `prune_closed_batches`) instead of the generic regex. Quick win.
3. B — `.gate_armed` marker + shell pre-filter + `async` on SessionEnd /
   PostToolUse Write. Biggest perceived gain.
4. D — systemMessage + scaled threshold + interval.
5. C — SessionStart digest + simplification of `crew-start` step 1.
6. A — template slimming, last (depends on what C/D add to the
   context, requires a `crew-update` migration).

Problem files: `crew/PROBLEMS/` (see INDEX.md regenerated by the hook).

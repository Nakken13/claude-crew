# Adaptive test policy — design

Date: 2026-11-06 · Status: awaiting validation

## Intent and rationale

Today `/crew-close-task` (step 5) creates a `crew/TESTS/IA/` and/or
`crew/TESTS/DEV/` checklist on **every** closure, with no threshold, no setting,
and no way to say "no tests here". On top of that, `requesting-code-review`
+ `simplify` are imposed on every task "even one that looks small" (step 3),
whereas the routing in `CLAUDE.md` limits them to diffs > ~50 lines or
engine/auth/hook files: the skill and the rule are inconsistent.

Measured on a real project (mobile app `app-voyageo`, heavy usage):

| | Files | Lines | Checked boxes | Empty boxes |
|---|---|---|---|---|
| DEV checklists | 202 | 5,034 | 48 | 1,167 |
| IA checklists | 53 | 1,045 | 38 | 227 |

Fewer than 4% of DEV boxes were ever checked: the main cost is writing
checklists nobody rereads, plus pointless execution (emulators).
The skill should bring productivity, not overload context and tokens.

The skill is used by other people, on unknown projects: the solution must
fit in without heavy configuration and rely on
**judgment**, not on a stack → level table (an API can be
a throwaway prototype).

## Goals

- Drastically reduce the tokens spent on valueless checklists/tests/reviews,
  on any type of project.
- Keep (or even improve) quality: the checks that matter
  are still done, and done by a real test in the code when possible.
- Zero extra questions to the user at init (except in the hesitation case,
  see §4).
- Judgment that is visible and correctable in one line.

## Non-goals

- No stack → level table.
- No complex parsing: a single small non-engine markdown file
  (`TESTS_POLICY.md`), read directly by the skills.
- No automatic deletion of projects' existing checklists
  (any cleanup = a separate request).
- Does not change the `crew/` folder model or batching.

## Anti-goals (failure even if "it works")

- A behavior change silently imposed on an existing project.
- Questions asked after every task (the friction would replace the token
  cost).
- A grid that lets an invisible and serious defect (auth, money,
  data) through with no verification at all.

## Design

### 1. Setting: dedicated file `crew/CLAUDE_CONTEXT/TESTS_POLICY.md`

**Decision validated by the user** (following the builder check): the setting
lives in a small **non-engine** file, because `CLAUDE.md` is in
`ENGINE_FILES_COMMON` (`crew/crew_update.py`): an edited `CLAUDE.md` would be
classified as `conflict` or overwritten by `/crew-update`. `TESTS_POLICY.md` is not
in the engine list, so `/crew-update` never modifies it; it is created
once (init or update) and then belongs to the user. `CLAUDE.md`
(template and root) contains only a one-line pointer to this
file in the routing / TESTS section; the skills read it (≈10 lines).

File content (a few lines):

- `Niveau : none | light | full`
- `Zones risquées :` free-form list, in the project's own words.

Meaning of the levels (they only move the **threshold**):

- `none`: never a checklist unless the user explicitly asks.
- `light` (**universal default**): the judgment grid (§3) decides task by task.
- `full`: current behavior (checklist on every closure). Never inferred or
  proposed by default; activated by editing the `Niveau` line of
  `TESTS_POLICY.md`.

**Missing file = historical behavior (`full`)** (review feedback): since the
skills ship with the plugin, an existing project without `TESTS_POLICY.md`
must not change behavior silently. The skills remind the user of this at
closure ("`/crew-update` to enable it"); `/crew-status` then applies its
safeguard.

### 2. Determination at init and update, without questions

`/crew-init` already detects the stack (step 2) and collects the project
description (step 3). The AI **infers** from that description + the code:

- the posture: `light` by default; `none` only if the project is
  clearly low-stakes (e.g. showcase site, prototype);
- the list of risky zones (what would be costly if it broke without anyone
  noticing: payment, accounts/2FA, real time, permissions, data
  migrations…), in the project's own words.

Only **facts** are detected automatically: presence of a test suite,
a CI, a test command.

The result is **shown in the final report** ("Tests: `light`. Risky
zones: …. To change, edit the Test policy section of
`CLAUDE.md`"). Description too vague → `light` with no zones, the grid decides.

`/crew-update` on an existing project: adds the section **without overwriting anything**,
inferred from `CLAUDE.md` and the history, announces it explicitly and never
applies it silently; `CHANGELOG` documents the change.

### 3. Judgment grid at closure (`light` posture)

The AI asks itself three questions:

1. If it breaks, would I notice right away when using the product normally?
2. If it breaks unnoticed, is it serious or irreversible (money, data,
   security, user loss)?
3. Is it already covered by an automated test in the code?

Outcomes:

- Invisible defect **and** serious **and** not covered → checklist, **5 boxes
  maximum**, only for what the AI cannot run itself.
- Otherwise → **no checklist**, one line in `HISTORIQUE.md`:
  "Tests: none — <reason>, covered by <test>" (auditable judgment).
- The task's verification is a real test in the code (TDD, already in the
  routing), not a markdown checklist to work through later.
- A task touching a declared risky zone is treated as "serious".
- Real hesitation → §4.

### 4. Hesitation case: ask at the end of the task

When the grid does not settle it, the AI asks **one** short question at the end
of the task: *"Do you want me to verify, do you want to verify, or should we skip?"*

- "I verify" → the AI runs the verification itself (emulator included
  if needed) and records the result in `HISTORIQUE`.
- "I verify" (user) → checklist ≤ 5 boxes, or nothing written if
  the user says they will check by eye.
- "Skip" → `HISTORIQUE` line, nothing else.

Anti-friction safeguard: the question is asked only when the grid is
genuinely undecided, never as a reflex. Any answer can be remembered
as a zone (added to/removed from "Zones risquées") so the
same question is not asked again — exact form left to the builder's discretion.

### 5. Code review and `simplify` aligned with the routing

`/crew-close-task` step 3: `requesting-code-review` and `simplify` only
if the diff exceeds ~50 lines or touches an engine/auth/hook file (rule
already written in the routing of `CLAUDE.md`); otherwise `verification-before-completion`
is enough. Remove the "even one that looks small" wording.

### 6. Emulator / heavy execution

The emulator (or any heavy visual check) is launched only in `full`, or if
the user asks, or if they answer "I verify" in §4. The current
`CLAUDE.md` rule "frontend … visually validated before declaring
done" is reworded for consistency: applicable depending on the posture, not
systematically.

### 7. Self-correction safeguard in `/crew-status`

`/crew-status` flags the accumulation of never-checked boxes (threshold to be
defined by the builder, e.g. > N empty boxes or a very low checked/empty ratio):
"1,167 DEV boxes never checked: switch to `light`?". Read-only,
suggestion only.

## Files concerned (indicative)

`skills/crew-close-task/SKILL.md`, `skills/crew-init/SKILL.md`,
`skills/crew-update/SKILL.md`, `skills/crew-status/SKILL.md`,
`template/CLAUDE.md` (Test policy section + consistent routing/§ TESTS),
root `CLAUDE.md` (mirror of the template), `CHANGELOG.md`, possibly
`crew/crew_hook.py` if the §7 safeguard computation fits there, and the
existing hook tests.

## Left to the builder

- Exact wording of the "Test policy" section and of the grid.
- Precise threshold of the §7 safeguard and how it is computed.
- Form of the memorization of the §4 answers.
- Version number / `CHANGELOG` entry.
- Automated tests for what is testable (hook/status), without overdoing it.

## Decisions made by me (to be confirmed)

- Universal `light` default, `full` never proposed by default.
- `/crew-update` announces the section rather than applying it silently.
- Cap of 5 boxes per checklist.

### Clarifications from the builder check (my choices)

- **Hesitation (§4)**: the grid "does not settle it" only when the defect
  would be invisible **and** the severity or the test coverage is
  genuinely uncertain. It does not apply as soon as an answer is "no".
- **Timing of the question (§4)**: asked *before* writing the `HISTORIQUE`
  line and the checklist (step 5 of `/crew-close-task`), so as to
  never rewrite a line already written.
- **No one to ask** (subagent, closure launched by `/crew-start`):
  hesitation → checklist of 5 boxes maximum (cautious, low-cost option),
  never a blocking question.
- **Code review and `simplify` (§5)**: independent of the level. Threshold of
  ~50 lines / engine-auth-hook file for `none`, `light` and `full`. The
  levels only drive checklists and visual/emulator verification.
- **Visual verification (§6)**: `none` = none unless requested; `light` =
  decided by the grid; `full` = always. In `none`, no "Tests:" line in
  `HISTORIQUE` (zero bookkeeping).
- **`/crew-status` safeguard (§7)**: skill text, no new code.
  Counts `- [ ]` vs `- [x]` in `TESTS/IA` and `TESTS/DEV` (excluding
  `TESTS_DONE`). Triggers only if the level is `full` or absent
  (legacy project), never in `light`/`none`, so the
  suggestion is not repeated indefinitely.
- **Inference without a description (§2)**: reads only `CLAUDE.md`, `README` and
  the manifests, and does targeted `grep`s in `HISTORIQUE` (never a full
  read, 100-line rule). Otherwise `light` with no zones.

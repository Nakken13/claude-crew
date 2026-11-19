---
name: ux-intuitive
description: Use when specifying, deciding or critiquing a screen, component or flow and the end user must not have to think — choosing color roles, button variants/shapes/sizes, visual hierarchy, feedback and states, animation purpose/duration/easing, error prevention, or the emotional tone of a moment (payment, deletion, waiting, success, empty state). Symptoms — several buttons competing, a color used for two meanings, decorative animation, users unsure what is clickable or what just happened, cold or blaming error screens. Preloaded by the `designer` persona; not for writing UI code or final copy.
---

# ux-intuitive — the user should never have to think

**Core principle**: every element answers, without words, *what is this, what
will it do, what just happened*. If the user has to read, remember, compare or
guess, the design pushed work onto them. Decide with the rules below and **prove
it with the deliverables** — a verdict without them is incomplete.

The project's design system wins on *values* (hex, px, tokens); these rules win
on *roles and logic* — a system that breaks one (same color for two meanings,
two primaries) is a finding.

References in `${CLAUDE_SKILL_DIR}/references/` (unresolved path: Glob
`**/ux-intuitive/references/*.md` in the project, then under `~/.claude/plugins`).
Load **only when the trigger applies**; if one cannot be read, continue with
this file and name it.

- `platform-specs.md` — any numeric spec (targets, grid, type, breakpoints,
  iOS/Material chrome, desktop density, contrast, dark mode, forms), citing
  a UX law, or scoring a critique (Nielsen heuristics, severity 0-4).
- `expert-patterns.md` — dense screen, > ~5 choices, multi-step flow, edge
  states, or auditing an existing screen: cognitive load (Hick, progressive
  disclosure, chunking, recognition over recall, Tesler), mental models and
  information scent, natural mapping, attention (Von Restorff, serial
  position), edge states, anti-pattern catalog "if you see X, fix with Y".
- `emotional-design.md` — money, deletion, sensitive data, long wait, first
  success, failure, or product personality: Norman's three levels, building
  D4, reassurance before the action, blameless errors, measured delight, peak
  and end, warm empty states, hard limit (no guilt, fake urgency or scarcity).

## Mandatory deliverables

Any answer that specifies or critiques a screen, component or flow contains
D1-D5, restricted to the elements in scope. Existing tokens → map them to
roles, do not invent values. No screen in scope → write "no screen in scope",
no deliverable.

**D1 — Color roles** (one row per role used; never two rows with the same color)

| Role | Color / token | Used for | Never used for | Non-color double (icon, text, shape) |
|---|---|---|---|---|

**D2 — Button system** (one row per variant used)

| Variant | Use on this screen | Fill / shape | Height | Radius | Label (verb + object) | Position |
|---|---|---|---|---|---|---|

**D3 — Motion** (one row per animation; no row = no animation)

| Animation | Function (feedback / causality / continuity / attention) | Duration | Easing | Reduced-motion equivalent |
|---|---|---|---|---|

**D4 — Emotion map** (one row per key moment of the flow; ordinary moments need
no reference, `emotional-design.md` only for the high-emotion ones above)

| Moment | What the user feels | Target feeling | Design response |
|---|---|---|---|

**D5 — Zero-thinking checklist** — the 12 points at the end, each ✅ / ❌ (with
the fix) / n/a (with the reason).

## Essentials

### 1. Color = role
- One role per color, one color per role: primary action, destructive,
  success, warning, info, neutral, selection/current, focus ring.
- Primary color **only on actionable things** (and current selection as a
  tint) — never headings, illustrations, decorative borders. Semantic
  red/green/amber only for their meaning (red "sale" badge next to red
  "delete" = defect).
- 60 / 30 / 10: neutral surfaces / secondary surfaces + text / ≤ 10 % accent.
- States change **lightness, not hue**; disabled = lower contrast, not a grey
  that reads as "secondary". **Never color alone** — add icon, label or shape.
- Accent colliding with a semantic hue (blue brand vs info, red brand vs
  destructive): say so and resolve (info goes neutral, or destructive gets an
  icon + explicit verb and never sits next to a primary).

### 2. Button system

| Variant | Meaning | Look | Count per screen |
|---|---|---|---|
| Primary | The one action the screen exists for | Filled, accent | **Exactly 1** (0 on reading screens) |
| Secondary | Valid alternative | Outlined or tonal | 0-2 |
| Tertiary | Low-stakes, dismiss, "later" | Text only | as needed |
| Destructive | Irreversible or data-losing | Danger color; filled only on the final confirmation (the only filled button there, safe choice = secondary with default focus), outlined/text before | 0-1 |

- Shape encodes type, size encodes importance; one radius product-wide.
- Heights: large 48-56 px (touch primary), medium 40-44, small 32 (dense
  desktop only); hit area always ≥ 44 px (48 dp Android). Full-width primary on
  mobile, content-width on desktop.
- **Label = verb + object** predicting the result ("Pay €24"), never "OK" /
  "Submit"; a confirm dialog repeats the verb of the button that opened it.
- Constant position: primary at the same place across the flow (thumb zone on
  mobile, end of reading direction on desktop); destructive never where the
  primary was a screen ago. **Fitts**: important + frequent = bigger + closer
  (thumb's bottom third on touch; cursor position or a screen edge on
  desktop) — never a small, far primary.
- Acts = button, navigates = link; never one looking like the other.
- States: default, hover, focus, pressed, loading (keeps width, shows
  progress, blocks double-submit), disabled (visible reason nearby; incomplete form → stay
  enabled and show what is missing on tap), success.

### 3. Signifiers and consistency
- Clickable **looks** clickable (fill, border, underline, chevron); nothing else
  does. Icon alone only if universal (search, close, back, menu, share,
  settings, home), otherwise icon + label.
- Same look / word / place = same behavior everywhere. **Jakob**: follow
  platform conventions; a novel pattern must beat them by far and be learnable
  in one use.

### 4. Hierarchy and grouping
- Squint test: 1 focal point, then 2-3 groups — built with size, weight,
  contrast, space (in that order), not more colors or boxes.
- Proximity before borders (inner spacing < outer); same kind = same look.
  One emphasis per screen — two highlighted things = none.
  Order follows the user's task, not the data model.
- Misalignment, uneven spacing or radius are usability defects
  (aesthetic-usability), not cosmetics.

### 5. Feedback and system status
- Visible response < 100 ms where the user is looking (control first, toast
  second). **Doherty**: answer within 400 ms or show work — skeleton beyond
  ~300 ms, determinate progress beyond ~2 s, background + notification beyond
  ~10 s. Optimistic UI for reversible actions, never for payment.
- Loading, success, error, empty, offline = five distinct states; never a blank
  area or an endless spinner. Say what happened **and** what comes next, where
  the action was taken.

### 6. Motion with a job
- One function per animation (feedback, causality, continuity, attention —
  once, never looping), or delete it.
- Durations: press 100-150 ms; small state change 150-250; enter/leave 200-300
  (exit ≈ 75 % of enter); full screen 300-400. Desktop ≈ 30 % shorter. Nothing
  > 500 ms except a rare skippable celebration ≤ 1 s.
- Easing: enter ease-out, leave ease-in, move ease-in-out; linear only for
  progress and opacity. Elements appear from their trigger and return to it.
- Frequent action (ten times a day) → ≤ 150 ms or none. Motion never blocks
  input.
- **Reduced motion mandatory per D3 row**: movement, scale and parallax become
  a ≤ 150 ms fade or an instant change; the feedback itself is kept.

### 7. Error prevention, control and freedom
- Smart defaults (last choice, most common, location, today); constrain
  instead of validate (pickers, masks, disabled
  impossible dates). Impossible actions absent or disabled with the reason
  (incomplete ≠ impossible, see § 2).
- **Destructive never on one unprotected tap**: reversible → do it + Undo, no
  "Are you sure?"; irreversible → confirmation naming the consequence, safe
  choice as default.
- Every screen, sheet, dialog and flow has an obvious exit that works at any
  step and **loses no data** (drafts kept, progress restored).
- **Postel**: accept liberally (trim, normalize formats, paste), display
  strictly (one format per data type). Never clear a form on error.
- Errors next to the field, no jargon or codes, one sentence: what is wrong
  and how to fix it. Empty states say what the screen is for + one start button.

### 8. Accessible by default (floor, not an option)

| Rule | Value |
|---|---|
| Text contrast | ≥ 4.5:1 (≥ 3:1 for large text ≥ 24 px / 18.66 px bold) |
| UI components, focus ring | ≥ 3:1; focus always visible |
| Touch target | ≥ 44×44 px web and iOS (44 pt), ≥ 48×48 dp Android; ≥ 8 px apart |
| Keyboard | Everything reachable and operable, logical tab order, no trap |
| Text | Body ≥ 16 px on web (inputs too), never < 12 px; survives 200 % zoom / Dynamic Type |
| Screen reader | Every control has a name; status changes are announced |
| Spacing | 4/8 grid: 4, 8, 12, 16, 24, 32, 48, 64 |

## Expert layer (summary — detail in `expert-patterns.md`)

- **Hick**: each extra option slows the decision — one decision per step,
  few options per screen, one recommended.
- **Progressive disclosure**: only the essential up front; advanced options
  behind one click or a drawer.
- **Chunking (Miller)**: group information in blocks of at most 5-7 items,
  each with a label, so the screen can be scanned.
- **Recognition over recall**: keep options and states visible (recent,
  suggestions, current value, recap) — never make the user remember
  something from a previous screen.
- **Tesler**: complexity that cannot be removed is absorbed by the system
  (totals, deadlines, formats, eligibility), never left to the user.
- **Critique of an existing screen**: Nielsen's heuristics, each problem
  rated for severity 0-4 and ranked by impact/effort.
- **Mental model and information scent**: labels use the user's words and
  predict the destination; the structure mirrors how users think about the
  task, not how the database is built.
- **Natural mapping**: a control sits next to what it affects and moves in
  the direction of its effect.
- **Attention**: one isolated element is remembered (Von Restorff) — spend
  it on the primary action; **serial position**: the most important
  entries go at the very start or very end of a nav bar or list, never the
  middle; key content on the F/Z reading path.
- **Edge states** are designed, not left over: empty, first use, error,
  offline, permission denied, too much content, too long text, slow network.
  Each offers a next action.

## Emotional design (summary — detail in `emotional-design.md`)

- Judge each screen on Norman's three levels: **visceral** (first-second
  impression: does it look trustworthy and calm?), **behavioral** (does
  using it feel effortless and under control?), **reflective** (what will
  the user remember and tell?).
- **Map the emotions of the flow** (D4): where is the user anxious, unsure,
  impatient, proud? The design answers the feeling, not only the task.
- **Anxiety moments** (payment, deletion, sensitive data, waiting): reassure
  *before* the action — what will happen, what it costs, how to undo — with
  trust signals at the exact point of doubt.
- **Blameless errors**: the product takes responsibility, stays calm, and
  shows the way out. Never "invalid", "illegal", "you failed to".
- **Measured delight**: celebration proportional to the user's effort,
  reserved for rare achievements, never on frequent actions, never delaying
  the next step, always skippable.
- **Peak and end**: polish the best moment and the last impression of each
  session more than the average.
- **One personality** (shape, motion, tone) across the product, that steps
  back in serious moments (money, errors, loss).
- Empty and waiting states are occasions for warmth and orientation.
- **Hard limit**: emotion serves the user. No guilt, fake urgency, fake
  scarcity or shaming to drive a metric — refuse and offer the honest
  alternative.

## D5 — Zero-thinking checklist

1. One primary action per screen, recognizable in under a second, large and
   within easy reach (Fitts).
2. Each color carries exactly one role; no status relies on color alone.
3. Each button look means one thing; labels are verb + object.
4. Everything clickable looks clickable; nothing else does.
5. Same look, word and position = same behavior everywhere; platform
   conventions followed (Jakob).
6. Squint test passes: one focal point, groups of ≤ 5-7 items, careful alignment.
7. Few options per screen; advanced ones on demand; nothing to remember from a
   previous screen.
8. Feedback < 100 ms, answer or visible work within 400 ms; loading / success /
   error / empty / offline designed.
9. Every animation has a named function and a reduced-motion equivalent.
10. Errors prevented first; when they happen, blameless, jargon-free, with the
    fix. Every screen has an exit that loses no data; destructive actions are
    confirmed or undoable.
11. Accessibility floor met: contrast ≥ 4.5:1, targets ≥ 44×44 px (48 dp
    Android), full keyboard operation, visible focus.
12. Anxious moments reassured before the action; the flow ends on a clear,
    positive confirmation.

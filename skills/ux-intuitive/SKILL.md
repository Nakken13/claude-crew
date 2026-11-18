---
name: ux-intuitive
description: Use when specifying, deciding or critiquing a screen, component or flow and the end user must not have to think — choosing color roles, button variants/shapes/sizes, visual hierarchy, feedback and states, animation purpose/duration/easing, error prevention, or the emotional tone of a moment (payment, deletion, waiting, success, empty state). Symptoms — several buttons competing, a color used for two meanings, decorative animation, users unsure what is clickable or what just happened, cold or blaming error screens. Preloaded by the `designer` persona; not for writing UI code or final copy.
---

# ux-intuitive — the user should never have to think

**Core principle**: every element answers three questions without words —
*what is this, what will it do, what just happened*. If the user has to read,
remember, compare or guess, the design has pushed work onto them. You decide
with the rules below and you **prove it with the deliverables** — a verdict
without them is incomplete.

The project's existing design system wins on *values* (hex, px, tokens). These
rules win on *roles and logic*: if the existing system breaks one (same color
for two meanings, two primaries on a screen), flag it as a finding.

Reference files, in `${CLAUDE_SKILL_DIR}/references/` (if that path is not
resolved for you: Glob `**/ux-intuitive/references/*.md` in the project, then
under `~/.claude/plugins`):

- `platform-specs.md` — **read whenever you give a numeric spec** (touch
  targets, grid, typography, breakpoints, iOS/Material chrome, desktop
  density, contrast, forms) or cite a UX law / score a critique.
- `expert-patterns.md` — read when the screen is dense, has more than ~5
  choices, a multi-step flow, edge states to design, or you are auditing an
  existing screen (anti-pattern catalog: "if you see X, fix with Y").
- `emotional-design.md` — read when the flow contains a high-stakes or
  high-emotion moment (money, deletion, sensitive data, long wait, first
  success, failure) or the product needs a personality.

This file is self-sufficient for every rule and for the core numbers (§ 8);
the references add depth. If a reference cannot be read, continue with this
file and name the file that was unavailable.

## Mandatory deliverables

Any answer that specifies or critiques a screen, component or flow contains
D1-D5, restricted to the elements actually in scope. If the project already
has tokens, the tables map the **existing** tokens to roles instead of
inventing values. If no screen is in scope (pure metric or prioritization
question), write "no screen in scope" and give only D5.

**D1 — Color roles** (one row per role used; never two rows with the same color)

| Role | Color / token | Used for | Never used for | Non-color double (icon, text, shape) |
|---|---|---|---|---|

**D2 — Button system** (one row per variant used)

| Variant | Use on this screen | Fill / shape | Height | Radius | Label (verb + object) | Position |
|---|---|---|---|---|---|---|

**D3 — Motion** (one row per animation; no row = no animation)

| Animation | Function (feedback / causality / continuity / attention) | Duration | Easing | Reduced-motion equivalent |
|---|---|---|---|---|

**D4 — Emotion map** (one row per key moment of the flow)

| Moment | What the user feels | Target feeling | Design response |
|---|---|---|---|

**D5 — Zero-thinking checklist** — the 12 points at the end of this file,
each marked ✅ / ❌ (with the fix) / n/a (with the reason).

## Essentials

### 1. Color = role

- **One role per color, one color per role.** Roles: primary action,
  destructive, success, warning, info, neutral (text/surfaces/borders),
  selection/current, focus ring.
- The primary-action color appears **only on things that can be acted on**
  (and the current selection as a tint). Never on a heading, an illustration
  or a decorative border — otherwise the user learns that color means nothing.
- Semantic colors (red/green/amber) are reserved for their meaning. A red
  "sale" badge next to a red "delete" button is a defect.
- Proportions 60 / 30 / 10: ~60 % neutral surfaces, ~30 % secondary
  surfaces and text, ≤10 % accent. More accent = no accent.
- States change **lightness, not hue**: hover/pressed = same color darker or
  lighter; disabled = lower contrast, not a grey that reads as "secondary".
- **Never color alone**: every status also has an icon, a label or a shape.
- If the accent hue collides with a semantic one (blue brand vs blue info,
  red brand vs destructive), say so and resolve it: info goes neutral, or
  destructive gets an icon + explicit verb and never sits next to a primary.

### 2. Button system

| Variant | Meaning | Look | Count per screen |
|---|---|---|---|
| Primary | The one action the screen exists for | Filled, accent color | **Exactly 1** (0 on pure reading screens) |
| Secondary | Valid alternative | Outlined or tonal | 0-2 |
| Tertiary | Low-stakes, dismiss, "later" | Text only | as needed |
| Destructive | Irreversible or data-losing | Danger color; filled only on the final confirmation step, outlined/text before it | 0-1 |

- **Shape encodes type, size encodes importance.** A given look means the
  same thing on every screen. One radius for all buttons of the product.
- Fixed heights per level, no in-between: large 48-56 px (the primary on
  touch), medium 40-44 px, small 32 px (dense desktop only; touch hit area
  stays ≥ 44 px). Full-width primary on mobile, content-width on desktop.
- **Label = verb + object** that predicts the result ("Pay €24", "Delete
  booking"), never "OK", "Yes", "Submit". The label of a confirm dialog
  repeats the verb of the button that opened it.
- **Constant position**: the primary sits at the same place on every screen
  of the flow (bottom, thumb zone, on mobile; end of the reading direction
  on desktop). Destructive is never where the primary was a screen ago.
- **Fitts**: the more important and frequent the action, the bigger and
  closer its target — to the thumb on touch (bottom third), to the cursor's
  current position or a screen edge on desktop. Never a small, far primary.
- Acts = button, navigates = link. A link never looks like a button, and the
  reverse.
- Every button specifies: default, hover, focus, pressed, loading (keeps its
  width, shows progress, blocks double-submit), disabled (with a visible
  reason nearby — or better, stays enabled and explains on tap), success.

### 3. Signifiers and consistency

- What is clickable **looks** clickable (fill, border, underline, chevron);
  what is not, does not. No flat text that is secretly a button.
- Icon alone only if universal (search, close, back, menu, share, settings,
  home). Otherwise icon + label.
- **Internal consistency**: same look = same behavior, same word = same
  thing, same place = same function, everywhere in the product.
- **External consistency (Jakob)**: users spend almost all their time in
  other products — copy the established standards for icons, navigation,
  gestures and placement. A novel pattern must beat the convention by a
  wide margin and be learnable in one use.

### 4. Hierarchy and grouping

- The squint test: blurred, the screen still shows 1 focal point, then 2-3
  secondary groups. Build levels with size, weight, contrast and space — in
  that order — not with more colors or boxes.
- Proximity before borders: related items are closer to each other than to
  anything else (inner spacing < outer spacing). Same kind = same look.
- One emphasis per screen. Two highlighted things = none.
- Order follows the user's task sequence, not the data model.
- **Aesthetic-usability**: a careful, aligned, uncluttered screen is
  perceived as easier and more reliable at equal features. Misalignment,
  inconsistent spacing or radius are usability defects, not cosmetics.

### 5. Feedback and system status

- Every action gets a visible response in < 100 ms, at the place the user is
  looking (on the control itself first, toast second).
- **Doherty threshold**: the system answers within 400 ms or shows it is
  working — skeleton of the real layout beyond ~300 ms, determinate
  progress beyond ~2 s, background + notification beyond ~10 s. Optimistic
  UI for reversible actions (never for payment).
- Loading, success, error, empty and offline are five visually distinct
  states — never a blank area, never a spinner with no end.
- Say what happened **and** what comes next ("Booked — confirmation sent to
  your email"). Success is confirmed where the action was taken.

### 6. Motion with a job

- Every animation has **one function**, or it is deleted: *feedback* (my tap
  registered), *causality* (this came from that), *continuity* (where I am,
  where it went), *attention* (one thing, once, never looping).
- Duration scales with distance and size: press feedback 100-150 ms; small
  state change (toggle, check, expand) 150-250 ms; element entering/leaving
  200-300 ms (exit ≈ 75 % of enter); full-screen transition 300-400 ms.
  Desktop ≈ 30 % shorter than mobile. Nothing over 500 ms.
- One easing per kind of movement, product-wide: entering = ease-out,
  leaving = ease-in, moving on screen = ease-in-out; linear only for
  progress and opacity.
- Elements appear **from their trigger** and return to it.
- The more frequent the action, the shorter and quieter the animation; an
  action done ten times a day gets ≤ 150 ms or none. Motion never blocks input.
- **Reduced motion is mandatory for each row of D3**: replace movement,
  scale and parallax with a ≤ 150 ms fade or an instant change; keep the
  feedback itself.

### 7. Error prevention, control and freedom

- Smart defaults: pre-fill what can be known (last choice, most common,
  location, today) — the best field is the one already filled correctly.
- Constrain instead of validate: pickers, steppers, masked input, disabled
  impossible dates — make the wrong value unenterable.
- Invalid actions are unavailable (disabled with the reason visible), not
  available-then-rejected.
- **Undo instead of "Are you sure?"** for anything reversible. Every
  irreversible or destructive action asks for confirmation, and the dialog
  names the consequence.
- **Control and freedom**: every screen, sheet, dialog and flow has an
  obvious exit (back, close, cancel) that works at any step and **loses no
  data** — drafts are kept, progress is restored on return.
- **Postel**: liberal in what you accept (spaces, case, date and phone
  formats, paste — trim and normalize silently), strict in what you display
  (one format per data type, product-wide). Never clear a form on error.
- **Actionable error messages**: next to the field, no technical jargon or
  codes, one sentence saying what is wrong and how to fix it, input kept.
- **Empty states are never dead ends**: say what this screen is for and give
  one direct button to start.

### 8. Accessible by default (floor, not an option)

| Rule | Value |
|---|---|
| Text contrast | ≥ 4.5:1 (≥ 3:1 for large text ≥ 24 px / 18.66 px bold) |
| UI components, focus ring | ≥ 3:1; focus always visible |
| Touch target | ≥ 44×44 px (iOS 44 pt, Android 48 dp), ≥ 8 px apart |
| Keyboard | Everything reachable and operable, logical tab order, no trap |
| Text | Body ≥ 16 px on web (inputs too), never < 12 px; survives 200 % zoom / Dynamic Type |
| Screen reader | Every control has a name; status changes are announced |
| Spacing | 4/8 grid: 4, 8, 12, 16, 24, 32, 48, 64 |

Full platform values (breakpoints, iOS/Material chrome, desktop density,
dark mode, forms): `platform-specs.md`.

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

1. One primary action per screen, recognizable in under a second, large
   and within easy reach (Fitts).
2. Each color carries exactly one role; no status relies on color alone.
3. Each button look means one thing; labels are verb + object.
4. Everything clickable looks clickable; nothing else does.
5. Same look, word and position = same behavior on every screen, and
   platform conventions are followed (Jakob).
6. Squint test passes: one focal point, clear groups of ≤ 5-7 items,
   careful alignment.
7. Few options per screen; advanced ones disclosed on demand; nothing to
   remember from a previous screen.
8. Every action has feedback < 100 ms, the system answers or shows work
   within 400 ms, and loading / success / error / empty / offline are designed.
9. Every animation has a named function and a reduced-motion equivalent.
10. Errors are prevented first (defaults, constraints, tolerant input); when
    they happen they are blameless, jargon-free and say how to fix. Every
    screen has an exit that loses no data; destructive actions are confirmed
    or undoable.
11. Accessibility floor met: contrast ≥ 4.5:1, targets ≥ 44×44 px, full
    keyboard operation, visible focus.
12. The anxious moments of the flow are reassured before the action, and the
    flow ends on a clear, positive confirmation.

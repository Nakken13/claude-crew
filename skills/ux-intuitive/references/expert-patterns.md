# Expert patterns

Decision rules for dense screens, long flows, edge states and audits. Each
rule states the observable trigger and the fix.

## Cognitive load

- **One decision per step.** If a screen asks two unrelated questions, split
  it or give one a default. A step the user can answer without thinking is
  cheaper than a shorter flow that makes them think.
- **Hick**: decision time grows with the number of equally weighted options.
  More than ~5-7 visible choices → recommend one (pre-selected or
  highlighted), group the rest, or hide the rare ones behind "More".
- **Chunking (Miller)**: break long numbers, long forms and long lists into
  groups of at most 5-7 items with a visible label per group. A 12-field form becomes 3 labelled
  groups of 4, not 12 equal rows.
- **Recognition over recall**: show recent items, suggestions, examples and
  the current value. Never ask the user to remember something shown on a
  previous screen — carry it forward (recap, breadcrumb, persistent summary).
- **Progressive disclosure**: the default view serves the 80 % case;
  advanced options are one explicit click away, never mixed in. Disclosure
  is stable: what was opened stays opened on return.
- **Working-memory rule**: a comparison requires both items visible at the
  same time. If the user must flip between two screens to compare, redesign.
- **Tesler**: every piece of complexity is paid by someone. If the system can
  compute it (total, deadline, format, timezone, eligibility), the user must
  never have to.

## Mental models and information scent

- Labels use the words users say, not internal names. If the team's name
  for the feature differs from the user's, the user's wins.
- A label must predict what is behind it. "Settings", "More", "Manage" have
  weak scent — name the content ("Notifications and privacy").
- Navigation structure mirrors user tasks ("Book", "My bookings"), not the
  data model ("Courts", "Slots", "Transactions").
- One concept = one word everywhere. "Booking" on one screen and
  "Reservation" on the next reads as two different things.
- Show where the user is, where they came from and how to go back, on every
  screen deeper than level 1.

## Affordances and natural mapping

- The control sits next to what it changes (edit button on the item, not in
  a toolbar far away).
- Direction matches effect: slider right = more, swipe direction = where the
  item goes, the sheet closes toward where it came from.
- Order of controls matches the spatial or temporal order of what they
  control (steps left→right, earlier→later).
- Gestures are accelerators, never the only way: every swipe, long-press or
  drag has a visible equivalent.

## Attention

- **Von Restorff**: the one element that differs is the one remembered.
  Spend that difference on the primary action or the single critical
  warning. Badges, banners and "new" tags everywhere cancel each other.
- **Serial position**: first and last items are remembered best. Put the
  most used entries at the ends of a tab bar or menu; never bury the key
  action in the middle of a list.
- **Reading path**: text-heavy screens are scanned in F (headings and line
  starts), sparse screens in Z (top-left → top-right → bottom-left →
  bottom-right). Key information on the path, primary action at its end.
- **Banner blindness**: anything that looks like an ad or a generic banner
  is skipped. Critical messages go inline, next to what they concern.
- **Change blindness**: a change far from the user's focus goes unseen.
  Updates appear where the eye is, or are announced there.

## Edge states (design each one, each offers a next action)

| State | Must show | Next action |
|---|---|---|
| Empty / first use | What will be here and why it is worth it | The single action that fills it |
| Loading | Skeleton of the real layout (not a centered spinner) | Cancel if > 10 s |
| Partial / slow | What is loaded, what is still coming | Keep interacting with what is there |
| Error | What happened in plain words, the user's input intact | Retry, or the alternative path |
| Offline | What still works, what is queued | Automatic retry announced |
| Permission denied | Why it is needed, what is lost without it | Open settings, or continue without |
| No results | The query as understood, why nothing matched | Relax a filter, suggestion |
| Too much content | Counts, truncation with a way to see all | Search, filter, pagination |
| Extreme text | Long names, translations +30 %, 200 % zoom | Wraps or truncates without overlap |
| Success | What was done, what happens next | The logical next step |

## Anti-pattern catalog — if you see X, fix with Y

| X (symptom) | Y (fix) |
|---|---|
| Two or more filled buttons on one screen | Keep one primary; demote the rest to secondary/tertiary |
| "OK / Cancel", "Yes / No" in a dialog | Verb + object on both ("Delete booking" / "Keep booking") |
| Same color for brand decoration and for actions | Reserve the accent for interactive elements |
| Red used for promo and for errors | Separate roles; promo gets its own non-semantic treatment |
| Status shown by color only | Add icon or label |
| Disabled button with no explanation | Explain inline, or keep it enabled and explain on tap |
| Placeholder used as label | Label above; placeholder only for format examples |
| "Are you sure?" on a reversible action | Do it, offer Undo |
| Confirmation dialog whose default is the destructive action | Default focus on the safe choice (secondary); the destructive is the only filled button |
| Icon-only toolbar with non-universal icons | Add labels (or tooltips on desktop + labels on touch) |
| Error message "Invalid input" / "An error occurred" | Say what is wrong and how to fix it, next to the field |
| Form cleared after an error | Preserve every value |
| Spinner with no end or centered on a blank page | Skeleton, then progress, then background + notify |
| Toast as the only feedback for a critical result | Confirm in place; toast only for low-stakes info |
| Animation that replays on every visit or loops | Play once, or remove |
| Animation > 150 ms on a frequent action | Cut to ≤ 150 ms or remove |
| Carousel hiding key content | Show the items, or a list |
| Hamburger menu hiding the 3-5 main destinations on mobile | Bottom tab bar |
| Modal on top of a modal | Inline expansion or a dedicated step |
| Different position of the primary action from screen to screen | Fix its position for the whole flow |
| Same word for two things, or two words for one thing | One concept = one word |
| Required information asked before any value is shown | Value first, ask at the moment it is useful |
| Celebration on a routine action | Reserve for rare achievements |
| Custom control replacing a native one without a strong reason | Use the native pattern |

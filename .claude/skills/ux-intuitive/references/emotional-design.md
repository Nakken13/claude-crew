# Emotional design

A product that works but feels cold, tense or blaming still makes the user
think — about whether to trust it. Emotion is designed with the same rigor
as layout: identify the feeling, decide the target feeling, specify the
response. It never becomes a lever against the user.

## Norman's three levels — what to check on each screen

| Level | Question | Levers |
|---|---|---|
| Visceral (first second, before reading) | Does it look trustworthy, calm, made with care? | Whitespace, alignment, restrained palette, image quality, consistent radius and elevation, no visual noise |
| Behavioral (while using) | Do I feel effective and in control? | Instant feedback, predictable results, undo, visible progress, no dead ends, speed |
| Reflective (afterwards) | What do I remember, what do I tell others, does it fit who I am? | The peak moment, the ending, what the user created or achieved, a recap worth sharing |

A defect on the visceral level (misalignment, clutter, aggressive color) is
read as "this product is not reliable" before any feature is tried.

## Building the emotion map (deliverable D4)

1. List the key moments of the flow in order (arrival, first input,
   commitment, wait, result, return).
2. For each: what does the user most likely feel? Typical: curious,
   unsure, impatient, anxious, relieved, proud, frustrated, bored.
3. Decide the target feeling (confident, reassured, in control,
   accomplished, calm).
4. Specify the design response — a concrete, observable element, not an
   adjective. "Total shown on the button, lock icon + 'Secure payment' next
   to the card field" — not "make it reassuring".

Example row: *Tapping "Pay"* → anxious (is it final? was I charged twice?) →
in control → button label carries the amount, switches to a loading state
in < 100 ms and cannot be tapped twice; cancellation rule stated just above;
success confirmed on the same screen with "confirmation sent to …".

## Anxiety moments — reassure before the action

| Moment | Fear | Response |
|---|---|---|
| Payment | Hidden cost, double charge, fraud | All-in total before the last step and on the button; trust signals at the card field; one-tap lock against double submit; receipt immediately |
| Deletion / cancellation | Losing something by mistake | Name exactly what is lost and what is kept; Undo when reversible; the safe choice is the default |
| Sensitive data (ID, health, location, contacts) | Misuse, exposure | Say why it is needed and who sees it, at the moment of asking; allow "not now"; show it can be changed later |
| Sign-up / commitment | Being trapped, spam | State what happens next and how to leave; no pre-checked opt-ins |
| Waiting | Is it stuck? Did it fail? | Progress that moves, what is being done, expected duration; beyond 10 s, let the user leave and notify |
| Irreversible send (publish, transfer) | Typos, wrong recipient | Recap before sending, short undo window after |
| Error after effort | My work is lost | Input preserved, plain cause, one clear way out |

Trust signals belong at the point of doubt (next to the field or button),
never in a footer nobody reads.

## Blameless errors

- The system takes the blame: "We couldn't read this card number" rather
  than "Invalid card number"; "That date is already past" rather than
  "Illegal date".
- Structure: what happened → what to do → (if useful) what was kept safe.
- Calm visual tone: one icon, the error role color on the field only — not a
  screen flooded in red. No exclamation marks, no caps, no technical codes
  in the primary message (code available in a secondary line for support).
- Never humor on an error that costs the user money, data or time.
- The wording itself is handed to `comms`; you specify intent, tone and
  maximum length.

## Measured delight

- **Proportional to effort**: finishing a 5-step setup, first success, a
  milestone → a real moment (illustration, short animation ≤ 1 s, warm
  line). Saving a setting → a checkmark.
- **Rare by construction**: a celebration seen every day becomes noise, then
  an obstacle. If the action is frequent, the reward is speed and silence.
- **Never in the way**: it does not delay the next step, is skippable by
  any tap, has a reduced-motion equivalent, and plays no sound by default.
- **Never in serious contexts**: money leaving, health, loss, errors.
- **Surprise is sparing**: small unexpected care (a remembered preference,
  a helpful default) beats confetti.

## Peak and end

People judge an experience by its most intense moment and its last one.

- Identify the peak (the moment the product delivers its value) and give it
  the most design attention: clarity, generosity of space, the one
  celebration of the flow.
- Design the end of each session: a clear confirmation, a summary of what
  was achieved, the obvious next step — never an abrupt return to a list.
- A negative peak (an error at the worst moment, a surprise fee) outweighs
  many good screens: fix the worst moment before polishing the average.

## Personality

- Choose 2-3 traits (for example: calm, direct, warm) and express them
  through the same three channels everywhere: **shape** (radius, density,
  weight), **motion** (snappy vs soft, see `SKILL.md` § 6), **tone**
  (intent handed to `comms`).
- Consistency beats intensity: a mild personality held on every screen
  feels more characterful than a strong one that comes and goes.
- The personality **steps back** in serious moments: payment, errors,
  loss, legal content are plain, calm and precise.

## Warm empty and waiting states

- Empty state: one sentence on what will appear here and why it is worth
  it, one action. An illustration only if it clarifies, never as filler.
- First use: the product does the first step with the user (sample data,
  template, pre-filled example) so they never face a blank page.
- Waiting: tell what is happening in human terms; for long waits, give
  something useful to read or do, or release the user and notify.

## Hard limit — emotion serves the user

Refuse, even on request, and propose the honest alternative:

- guilt or shame to prevent an exit ("No thanks, I don't care about my
  health");
- fake urgency or scarcity (invented countdowns, "2 left" that is not true);
- manufactured anxiety (alarming colors or wording on a routine choice);
- affection used to retain (sad mascot when unsubscribing);
- hiding the real cost of an action behind a reassuring tone.

A real constraint may be shown (a slot genuinely held for 10 minutes) —
state it plainly, without alarm styling. Test: would the user thank you for
this element if they knew exactly why it is there?

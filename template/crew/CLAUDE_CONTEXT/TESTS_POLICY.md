# Test policy

File owned by the project: `/crew-update` never modifies it. Single source
of the test rules, read by `/crew-close-task` and `/crew-status`.
Edit freely.

(The two keys below stay in French because skills match on them: `Niveau :` = level, `Zones risquées :` = risky zones.)

Niveau : light

Zones risquées : (none filled in)

## Levels

- `none`: never a checklist nor a "Tests:" line, no visual/emulator
  verification, unless explicitly requested.
- `light` (default): the grid below decides task by task.
- `full`: a checklist at every closure and systematic visual verification
  (historical behavior).

The level only drives checklists and visual/emulator verification.

## Risky zones

What would be costly if it broke without anyone noticing (payment,
accounts/2FA, real time, permissions, data migrations...).
`/crew-init` or `/crew-update` replace the `Zones risquées :` line with the
list inferred from the project, in its own words. Touching a zone = "serious".

## Grid (`light` level)

At closure, three questions:

1. If it breaks, would it be seen right away when using the product normally?
2. If not, is it serious or irreversible (money, data, security, user loss,
   risky zone)?
3. Is it already covered by an automated test in the code?

- Invisible **AND** serious **AND** not covered → `TESTS/IA` or
  `TESTS/DEV` checklist, **5 boxes maximum**, only what the AI cannot run
  itself.
- Otherwise → no file; one line in `HISTORIQUE.md`:
  `Tests: none — <reason>, covered by <test>`.

## Hesitation (`light` level)

Only if the defect would be invisible **and** the severity or coverage is
genuinely uncertain: ask **one** short question, before writing the
`HISTORIQUE` entry or the checklist — "Shall I check, will you check, or do we skip?".

- "I check" → the AI runs it (emulator included if needed) and notes the
  result in `HISTORIQUE`.
- "You check" → checklist ≤ 5 boxes, or nothing written if it is by eye.
- "Skip" → `HISTORIQUE` line, nothing else.

With no one to ask (subagent, closure chained by `/crew-start`):
checklist ≤ 5 boxes, never a blocking question. The emulator or any heavy
visual verification only runs in `full`, on request, or after
"I check".

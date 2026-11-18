# Platform specs and arbitration principles

Give numeric values, not "big enough". Default references — the project's
design system prevails if it defines others.

## Touch targets and interaction

- iOS: 44×44 pt min. Android/Material: 48×48 dp min, ~8 dp between targets.
- Web: WCAG 2.2 AA 24×24 CSS px min (2.5.8), aim for 44×44 px on touch.
- Thumb zone (mobile): primary actions in the bottom third of the screen;
  destructive actions out of reach of accidental taps.

## Grid and spacing

- 4/8 pt grid: spacing 4, 8, 12, 16, 24, 32, 48, 64.
- Mobile side margins 16 px (20 pt common on iOS); desktop, container max
  1200-1440 px; reading column max ~680-720 px.

## Typography

- Web: body 16 px min (and **16 px min on inputs** to avoid iOS Safari
  auto-zoom), line height 1.4-1.6, line length 45-75 characters.
- iOS: body 17 pt, caption min 11 pt, support Dynamic Type.
- Android: body 14-16 sp, always in sp to respect the system scale.
- Modular scale ratio 1.2-1.333; 2 families max; web: text never below 12 px.

## Web breakpoints (mobile-first)

Design first at 360-390 px, then 640 / 768 / 1024 / 1280 / 1536 (Tailwind
convention) — also check 320 px (small Android, 200% zoom).

## Mobile — system chrome

- iOS: navigation bar 44 pt, tab bar 49 pt (+34 pt home indicator on devices
  without a button), respect safe areas; 3-5 tabs max.
- Material 3: top app bar 64 dp, navigation bar 80 dp, FAB 56 dp;
  navigation rail/drawer on tablet and large screens.
- Do not port iOS patterns to Android (and vice versa): system back, sheets,
  action placement, native typography.

## Desktop software / dense web apps

- Reference minimum window 1280×720 (tolerate 1024×768); sidebar 240-280 px,
  collapsible.
- Density: table rows 32-36 px (compact) / 40-48 px (comfortable), offer the
  setting if usage is intensive.
- Keyboard shortcuts for frequent actions, distinct hover/focus/selection
  states, context menu, undo rather than modal confirmation.

## Color, contrast, states

- WCAG AA: 4.5:1 normal text, 3:1 large text (≥24 px or ≥18.66 px bold),
  3:1 UI components and focus indicator. Never color alone to carry
  information.
- Dark mode: neither pure black (#000) backgrounds nor pure white text —
  background ~#121212, lighter elevated surfaces, desaturated accent colors.
  Roles stay identical between light and dark; only the values change.
- Each component specifies its states: default, hover, focus, pressed,
  disabled, loading, error, empty.

## Forms

Single column, labels above (never placeholder alone), 44-48 px tall fields,
inline validation on blur, right keyboard type (`inputmode`, `autocomplete`),
errors that say how to fix.

## Motion (base values — rules and functions in `SKILL.md` § 6)

Micro-interactions 100-200 ms, transitions 200-400 ms, ease-out on enter /
ease-in on exit, `prefers-reduced-motion` respected for every animation
(choice of implementation skill → § Skill routing in `CLAUDE.md`).

## Principles for arbitrating

- UX laws to cite when they really settle it: Fitts (target size/distance),
  Hick (number of choices), Jakob (users expect the conventions of other
  products), Tesler (irreducible complexity must be absorbed by the system,
  not the user), serial position, aesthetic-usability.
- **One primary CTA per screen**; hierarchy readable when squinting;
  progressive disclosure rather than showing everything up front.
- WCAG 2.2 AA accessibility = floor, not an option: visible focus, screen
  reader labels, 200% zoom / Dynamic Type without breakage, logical tab
  order.
- Critique of an existing screen: Nielsen's heuristics, each problem rated
  for severity 0-4 and ranked by impact/effort.

# Design

The built page in `page/` is the target. This doc
is the system behind them. The owner rejected the first version as "super genérico y feo" and asked
for four anti-slop skills: Peter Yang's no-ai-slop, impeccable (pbakaus), better-ui (jakubkrehel)
and beUI motion (starc007/ui-components), and later web-animation-skills (iart-ai) for motion. Their rules, distilled with sources:
the first project's research notes (not in this repo).

## Concept: dark cockpit

From aviation overhead panels: nothing is lit while systems are normal; only an abnormal condition
lights. On screen: neutral and quiet at rest; amber (caution) and coral (warning) appear only on what
needs the owner, always with a word and an icon, never color alone. The aviation world lends only
the principle and the two state colors: no bezels, LED glows, segment fonts or terminal costume.

Scene: one engineer at a desk, all day, the cockpit beside dark Ghostty/herdr panes in a dim room,
glancing over every few minutes. Dark is chosen for that scene (and by the owner).

## Tokens (OKLCH, warm graphite at hue 80, very low chroma)

| Role | Value |
|---|---|
| Ground | `oklch(0.17 0.006 80)` |
| Surface (panels, list background) | `oklch(0.20 0.006 80)` |
| Raised / hover | `oklch(0.22 0.006 80)` to `oklch(0.24 0.006 80)` |
| Selected | `oklch(0.24 0.006 80)` + inset 1px `oklch(0.40 0.006 80)` |
| Input ground | `oklch(0.15 0.006 80)` |
| Lines (structure) | `oklch(0.27 0.006 80)`, `oklch(0.30 0.006 80)` |
| Control edge | `oklch(0.36 0.006 80)` to `oklch(0.38 0.006 80)` |
| Text 1 | `oklch(0.93 0.006 80)` |
| Text 2 | `oklch(0.74 0.006 80)` to `oklch(0.80 0.006 80)` |
| Text 3 (meta, sources) | `oklch(0.66 0.006 80)` (min 4.5:1 on ground) |
| Caution (amber) | `oklch(0.82 0.13 75)`; text on dark `oklch(0.86 0.11 75)`; fill `oklch(0.80 0.13 75 / 0.12)` |
| Warning (coral) | `oklch(0.72 0.16 38)`; solid lit cell `oklch(0.72 0.15 38)` with ink `oklch(0.18 0.03 38)` |
| Primary button | Text 1 fill with ground-colored text (no hue: hue means state only) |
| Focus ring | 2px Text-1-ish `oklch(0.88 0.05 80)`, offset 2px |

No blue (the observability cliché), no gradients except the half-filled criterion cell, no glow, no
glass, no shadows for depth (surfaces step by lightness).

## Type

- Atkinson Hyperlegible Next (400, 600) for all UI; Atkinson Hyperlegible Mono (400, 500) only for
  numbers, ids, commands and timestamps. Google Fonts. Chosen for legibility over long sessions.
- Sizes: 13 meta and sources, 14 table cells and secondary, 15 controls, 16 body, 18 key sentences,
  20 section headings (600). Body letter-spacing +0.01em (light on dark). Tabular numerals in data.
- Sentence case everywhere; the only caps are the light-strip status words in variant B.

## Layout and components

- No cards for everything: group by proximity and hairlines; a raised surface only for an opened
  row's detail, the light detail band and the milestone tiles.
- Needs you: one list; each row is level icon + word, one sentence, a source line, one action.
- Bars: 4px, neutral fill under the target, amber over it, a tick for the sweet spot or the 85% line.
- Milestone criteria: one 14px cell per criterion (filled, half, amber outline, empty), goal ringed.
- Buttons 44px high; segmented control for effort; real `<button role="switch">` toggles.
- Radii: 8 for controls, 12 for panels; nothing pill-shaped except switches.

## Motion (confirm an action, and show what is live)

The owner reads the team by sight, before any text ("soy una persona muy visual"), so
motion carries state: something moves only while it is really happening, and stops when it stops.
Rules from web-animation-skills (iart-ai: 60fps-animation, accessible-animation, micro-interaction).

Confirm an action:
- Press: scale 0.96, 150 ms, `cubic-bezier(0.16, 1, 0.3, 1)`; never on disabled controls.
- Row hover: background-color 100 ms ease-out, behind `@media (hover: hover)`.
- A result message enters: opacity and 4px rise, 180 ms; reduced motion: opacity only, 150 ms.
- Switch knob: translate 150 ms, same curve.
- A verified compaction or clear shrinks its context bar from before to after once, 400 ms, same
  curve. Until the compact_boundary record arrives, the bar breathes (opacity 1 to 0.45, 1.1 s).

Show what is live (loops; each one is a fact the collector read):
- Working glyph: three 3x14px bars before each session name. Busy: they rise and fall
  (scale 0.2 to 1, 900 ms, alternate, 300 ms apart). Idle: three flat dots in Text 3. Same glyph in
  the session panel heading.
- Working sweep: a busy row's bottom hairline carries a light that crosses it (2.4 s; 1.1 s while
  compacting). The only gradient besides the half-filled cell: transparent, Text 1 at 0.9,
  transparent.
- Each row has a fixed phase offset so busy rows never move in lockstep. Speed and phase carry no
  data; never map them to a number.
- Warning blinks until acted on (aviation master warning): the coral icon in Needs you, or the
  word on a lit light in B, opacity 1 to 0.45, 600 ms. Caution stays steady.
- In-progress done criterion: its half-filled cell breathes, 1.6 s.
- A busy session's dot on a milestone tile breathes, 2.4 s.
- Refresh line: 1px under the read time fills over the read period (30 s, linear) and restarts on
  each read. In the build, start it at the snapshot's read time, not the page load.

Limits:
- Animate only `transform`/`scale`/`translate` and `opacity` (compositor only); never width, left
  or shadows. Name transition properties, never `all`.
- Loops only on live state; nothing animates on load, and a refresh never replays an entrance.
- Reduced motion: every loop stops. The busy glyph stays as three bars of different heights and
  idle as flat dots, so the state still reads by shape; the sweep and refresh line hide.

## Copy

- One term per concept: session, bead, ask, sweet spot, compact, account N, done criterion, found work.
- Buttons are verb + object: "Compact ios", "Send 2 answers to brain", "Pause the team".
- Reasons as plain sentences with "so" or "because"; colons only for labels.
- No em dashes in the UI; empty cells stay blank or say "none".
- Every region ends with a short source line ("From cswap list --json, read 40 s ago").
- Loading names the operation and the proof awaited ("Waiting for its compact_boundary record").

## The two layouts

- A, one screen (`Main.dc.html`): Needs you, milestone with checks, sessions + session panel, asks
  with the embedded grill, accounts, autopilot. Has the latest content (milestone, grill). Two of its
  parts are gone from the build: the milestone checks ("Is the team on Mn?", cut by the owner on
  2026-10-16: its rules became the Needs you row "Team rules broken", the amber tile, the stuck mark
  and the Main light) and the Autopilot block (replaced by Background jobs, 2026-10-16).
- B, light strip and tabs (`Tabs.dc.html`): nine lights in a fixed order (position becomes memory),
  a detail band with the action, then tabs Sessions, Asks, Accounts, Autopilot. It does not have the
  milestone or the grill yet.
- Built (the owner, 2026-10-16, after a first tabbed build the owner found "desordenado, sobrecargado con
  texto": "un cockpit debe ser ordenado, compacto, usable"): B's light strip, then two columns that
  scroll by themselves. Every section is one shape: a header that opens and closes it, one-line
  rows in fixed columns, the row's detail (full text, source, controls) opened in place. Compact
  density: 32 px rows, 28 px buttons, 14 px body; it replaces the 44 px buttons and 16 px body
  above for this page (a desktop with a mouse; still over the 24 px minimum target size).
- The built page, top to bottom: header (read time to the second, sources not read, prices that
  differ from Anthropic's page, Pause the team); then the sections: the milestone and Your tasks
  (Actions, Questions, Tickets) on the left; Team health (one row per resource), Sessions, Accounts
  and Background jobs on the right. The lights strip is gone (the owner, 2026-10-16). A Needs you row carries its level word beside the icon, never the
  icon alone; a row the owner acted on dims to 0.6 with its result in place of its source.

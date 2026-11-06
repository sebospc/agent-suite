# Building the the project cockpit

Read `README.md`, then the doc for the part you are working on. Do not scan
`research/raw/` whole: it holds the sources behind the docs; open it only to check a claim.

## The owner

- Reply to the owner in English, even when they write in Spanish.
- The owner decides product and process questions. Ask before deciding anything the owner has not decided
  "Open questions". Anything that leaves the machine (push to a new place, deploy, a new paid
  service, sending team data to a third party) needs the owner's own yes.
- Work on `main` and push to `main` (the owner, 2026-10-16: "(the owner's words)"). No feature branches, no PRs. One cockpit session at a time; pull before you start.
- Never invent a number. Every value on screen comes from a source the cockpit reads, shows that
  source and its age, and says whether it is measured or a heuristic.

## Purpose rule (the owner: "(the owner's words)")

Every element must change a decision the owner makes, or show why they can trust one. If it does
neither, it does not ship. `docs/REQUIREMENTS.md` lists each element with its purpose; adding an
element means adding its row there first.

## Design rule

The mockups in `design/` are the target. `docs/DESIGN.md` is the system they use and the
anti-slop rules behind it (no-ai-slop, impeccable, better-ui, beUI motion). Keep the tokens,
type, spacing and motion values exactly; they are not approximations.

## Engineering rules (same spirit as the the project repo)

- Strict hexagonal architecture: core logic depends only on ports; one adapter per technology
  (transcripts, herdr, bd, cswap, git, grill-with-ui); one composition root reads configuration.
  Every port has a real adapter and a test fake. Details: `docs/ARCHITECTURE.md`.
- Python 3 standard library only for the collector and server; one static HTML page with plain JS.
  No install step on the owner's Mac.
- One type per file, files under about 300 lines, folders by feature. Names carry the meaning;
  comments explain why, never what.
- Every non-trivial logic change leaves a test that fails if the logic breaks. Report real test
  counts ("N passed, M failed"), never "tests pass".
- Read-only first. Phase 1 writes nothing except an answered ask through `ask_owner.py answer`.
  Phase 2 (started 2026-10-16, the owner: "continúa con la siguiente fase") adds the owner's controls,
  typed into a session's pane only on the owner's click, each with the check that proves its effect.

## Never

- Never change `~/.claude*`, cswap state, or the balancer from the cockpit. Read them only.
  (cswap list and status are read-only and allowed.) The one exception (the owner, 2026-10-16), for
  this one setting: the autopilot types `/autocompact 1000000` when it turns on and
  `/autocompact 200000` when it turns off, once per model (Opus, Sonnet, Fable) per cswap account
  (each account has its own settings folder) into one live session of that pair, never while
  `~/.agent-board/paused` exists (a held step goes out once the file is gone). For Haiku it types
  its live sweet spot's window instead (the owner, 2026-10-17: the autopilot "(the owner's words)"). Claude Code saves it as `modelSettings.<model>.autoCompactWindow` in that account's
  settings file. Each one is logged in `actions.jsonl` and proved only by the session's next
  `compact_boundary`: a project settings file can override the saved value.
- Never touch the owner's iPhone or emulator-5556.
- Never print or log secrets (`.env.local`, OAuth tokens, keychain items).
- Never send a message to a session that the owner did not trigger, except the autopilot's rules (the
  owner turned them all on, 2026-10-16: "debe ser autobalanceado"), and log every one.

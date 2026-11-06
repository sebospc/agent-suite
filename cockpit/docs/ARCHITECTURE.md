# Architecture and phases

## Shape

A local web app on the owner's Mac, no install step:
- `collector`: reads every source on a 30 s cycle (transcripts incrementally by byte offset), computes
  the view model, keeps history in SQLite (stdlib `sqlite3`).
- `server`: Python stdlib `http.server` bound to `127.0.0.1` only; serves the page, `GET /api/snapshot`,
  and in phase 2 `POST /api/action` for the whitelisted controls.
- `page`: one static HTML file with plain JS, built from the first project's mockup (or the
  layout the owner picks). It polls the snapshot and renders; it never computes business rules.
- Start: `python3 cockpit.py` (prints the url).

## Hexagonal layout (mandatory, as in the the project repo, ADR 0007)

Core logic depends only on ports; adapters implement one technology each; one composition root picks
adapters from configuration. Every port has a real adapter and a test fake. Pure domain code gets no
interface. Folders by feature.

| Port | Real adapter | What it gives the core |
|---|---|---|
| Transcripts | JSONL reader over `~/.claude/projects/<slug>` with dedupe by `message.id` | per-session requests, compactions, messages, names |
| LiveSessions | cswap profile `sessions/<pid>.json` scan plus herdr pane list | session ↔ pid ↔ pane ↔ account, busy/idle |
| Board | `bd` CLI with timeout, `dod.json`, `goal.json`, `stack.json` | beads, milestones, criteria, goal |
| Asks | `panel.json` read, `ask_owner.py` for writes | open asks, answering |
| Accounts | `cswap list --json` (read-only) | quota per account with age |
| BalancerLog | the balancer's decision JSONL (when it exists) | why each account was chosen |
| Git | `git` CLI on the shared repo and `stack-brain` | gate result, unpushed commits |
| Panes (phase 2) | herdr `agent prompt` / `agent read` | sending /compact, /clear, /effort; reading status lines |
| Action log (phase 2, 3) | JSONL in `~/.cockpit` | every control sent and its proved outcome |
| Task classifier (phase 3) | Jev (TypeSafe), not connected yet | model and effort suggested per bead, shadow mode |
| Grill | `node server.mjs` of grill-with-ui | create, serve and patch a grill session; read events |
| Clock | system time | "now" for ages and staleness (never read time directly in core) |
| Pause | `~/.agent-board/paused` (exists while paused) | whether the team is paused; nothing is typed while it is |


Core features (no I/O): `milestone/` (criteria, checks), `sessions/` (working-on, drift),
`compaction/` (inputs, sweet spot, recommendations), `needs/` (the Needs you rules), `accounts/`,
`autopilot/` (rule evaluation, never acting itself: it returns intended actions the composition
root executes and logs).

Gang of Four only where it removes branching: Strategy for price cards (flat vs Haiku step), Adapter
for every source, Command for each control (execute + verify + log), Template method for the
"act then verify" cycle.

## Rules the code keeps

- Every number in the snapshot carries `source`, `read_at` and `kind` (measured | heuristic).
- A source that fails shows as unavailable with its error, never as zero.
- bd and herdr calls have timeouts; one slow source never blocks the page.
- Transcript parsing lives in one adapter with fixture tests (the format is internal and changes).
- Thresholds (6 h silent, 85% quota, 100k Haiku, 10 min idle) live in one config file with the
  owner's sign-off, not in code.

## Phases and done criteria

| Phase | What | Done when |
|---|---|---|
| 0. Calibration (half a day on the Mac) | Run `research/scripts/measure_context.py` on the real transcripts: g, y, P, F_s per session; compactions seen; Haiku requests over 100k. Fit quota weighting from `usage-samples.jsonl` | The numbers per session and the weighting are written to `docs/CALIBRATION.md` |
| 1. Read-only cockpit + answering asks | Needs you, milestone with 7 checks, sessions with working-on and sweet spot, accounts, autopilot log (empty), asks with the embedded grill | For 3 numbers per section, a manual check on the Mac matches; answering an ask moves it to `answered` with the owner's words |
| 2. Controls | Compact, clear at task end, effort, apply window via team.json, pause (needs team dependency 7) | Each control shows its before and after on screen, from the source, not from its own claim |
| 3. Autopilot and history | The two autopilot rules; history trends (milestone share of tokens per session per day); task classification with Jev (the owner's choice), first in shadow mode | A week of the autopilot log with actions and tokens saved |

## Tests

- Fakes for every port; fixtures in `fixtures/` for the board and transcript formats.
- One test per rule that fails if the rule breaks (each milestone check, each Needs you light, the
  sweet-spot math against the verifier's numbers (the first project's research data, not in this repo)).
- Report counts as `N passed, M failed, K skipped`.
- Run: `python3 -m unittest discover -s tests -t .` from the repo root (stdlib only).

# Plan: phase 0 and phase 1

Written 2026-10-16 from `ARCHITECTURE.md`, after the owner's answers (layout A, Jev for phase 3,
launches read `team.json`, thresholds start provisional and are set from phase 0 measurements).

## Phase 0: calibration on the owner's Mac

Three read-only scripts in `research/scripts/`. Each prints numbers only (never message content,
never emails or tokens), so the output is safe to paste back.

| Script | Reads | Prints | Fills |
|---|---|---|---|
| `calibrate_sessions.py` | `~/.claude/projects` | per session (id, name, model, TTL): requests, context now, g and y (trimmed means, last 50 main-thread turns), F, F_s, P, S, every `compact_boundary` (trigger, pre, post), Haiku requests over 100k, idle gaps between turns (p50, p90, share over 10 min and over 1 h) | `COMPACTION.md` inputs per session; the 10 min idle threshold |
| `calibrate_quota.py` | `~/.claude/handoff/state/usage-samples.jsonl` + `~/.claude/projects` | per account: consecutive sample pairs inside one 5h window, the 5h % delta, the token mix of the same interval (read, 1h write, 5m write, fresh, output, by model); least-squares weights per category; how many intervals could be attributed to one account | `COMPACTION.md` unknown 1; the balancer's `WEEKLY_PCT_IN_5H_PCT` and `COLD_TURN_PRO_PCT_PER_1K_TOKENS` |
| `measure_thresholds.py` | `~/.agent-board` (`panel.json`, `bd export`) | ask wait (asked to answeredAt) by kind, p50/p90; in-progress beads: longest gap between updates (started_at, comments, closed_at), p50/p90/p95; beads per assignee in progress at once; messages per bead where countable | silent bead (6 h), blocker ask (1 h), messages-per-bead floor |

Attribution of tokens to accounts (`calibrate_quota.py`) is the weak point: transcripts may carry
`session_context.userEmail`; when they do not, only intervals where exactly one account's 5h %
moved are used. The script reports how many intervals survived, so a thin fit is visible.

Done when the numbers are in `docs/CALIBRATION.md` and the owner has set each threshold in
`config/thresholds.json` from them.

## Phase 1: read-only cockpit and answering asks

### Layout (hexagonal, folders by feature, Python 3.9 compatible, stdlib only)

```
cockpit.py                    start: builds the composition root, serves, prints the url
config/thresholds.json        every threshold with value, status (provisional | set), source, date
.cockpit.json                 the project: port, Mac paths and commands, team; merged over ~/.config/cockpit/config.json
cockpit/
  composition.py              the one root: reads config, picks real or fake adapters
  clock/                      Clock port, system adapter, fixed fake
  transcripts/                Transcripts port, JSONL adapter (dedupe by message.id), fake; parsing lives only here
  live_sessions/              LiveSessions port, cswap records + herdr adapter, fake
  board/                      Board port, bd CLI adapter (timeout) + dod/goal/stack files, fake
  asks/                       Asks port, panel.json reader + ask_owner.py writer, fake
  accounts/                   Accounts port (cswap list --json), BalancerLog port (absent today), fakes; core view
  git/                        Git port, git CLI adapter, fake
  grill/                      Grill port, server.mjs adapter (create, patch, serve, read events), fake
  milestone/                  core: current milestone, criteria cells, what is left, the seven checks
  sessions/                   core: working-on kind, state, drift vs team.json
  compaction/                 core: inputs, sweet spot (price cards as Strategy), recommendation sentence
  needs/                      core: each Needs you rule as one object; Handled by itself; Clear
  snapshot/                   assembles the view model; every number as {value, source, read_at, kind}
  server/                     http.server on 127.0.0.1: page, GET /api/snapshot, POST /api/asks/grill
page/index.html, page/cockpit.css, page/cockpit.js   built from the first project's mockup
tests/                        unittest, against fixtures/ and fakes
```

The collector runs inside `cockpit.py` on a 30 s thread; each source has its own timeout and a
failing source shows "unavailable: <error>", never zero. History in SQLite waits for phase 3 (no
phase 1 element needs it; tokens 24h and today vs yesterday come from transcript timestamps).

### Sections and what each reads

| Section (mockup A) | Phase 1 content | Gap shown honestly until |
|---|---|---|
| Header | read time, refresh period | pause button arrives in phase 2 |
| Needs you | all nine rules in `REQUIREMENTS.md`; action buttons are copy-to-clipboard of the command or prompt (no control acts in phase 1) except Answer, which jumps to asks | backup light: dependency 6 |
| Handled by itself / Clear | sessions over their sweet spot while busy, accounts over 85%, main green, tokens today vs yesterday | duplicates line: pg-208g |
| Milestone | goal sentence, criteria cells, what is left, seven checks with evidence | none |
| Sessions table + panel | state, account, model, effort, context vs sweet spot, tokens 24h, working on; drift vs `team.json` when it exists | stable names: dependency 5; `team.json`: dependency 8 |
| Asks + embedded grill | open asks and owner beads without an ask; one grill round; answer writes via `ask_owner.py answer`; thread comments forwarded to the asking session through herdr only on the owner's send | none |
| Accounts | 5h and 7d with resets and 85% tick, sessions per account | "Why the balancer chose": pg-81e3 |
| Autopilot | rules listed, switches disabled, log empty, process line | phase 3 |

### Tests (each rule has one that fails if the rule breaks)

Transcript parsing and dedupe; context now and after a compact boundary; each of the seven checks;
each Needs you rule; sweet spot against the verifier numbers;
Haiku grid candidate; working-on kind; drift; ask to grill question mapping; answer path calls
`ask_owner.py answer` with the owner's words; a failing source yields unavailable, not zero.
Fixtures I add (compact boundary transcript, cswap list, herdr pane list, grill events) are built
from the formats in `DATA_SOURCES.md` and marked synthetic in `fixtures/README.md`.

### Done (from ARCHITECTURE.md)

For three numbers per section, a manual check on the Mac matches (the run guide lists the command
for each), and answering an ask moves it to `answered` with the owner's words.

## Status (2026-10-16, end of the first build session)

Done and pushed on branch `claude/trusting-mayer-97m7uz` (no PR yet):
- Phase 0: the three scripts ran on the Mac; results in `CALIBRATION.md`. Sweet spots use list prices (the
  data supports them over raw tokens). Quota per-kind weights are not reliable yet (refit near 300 windows).
- Phase 1: the read-only cockpit (`cockpit.py`, `cockpit/`, `page/`), 98 tests; phase 0 scripts 11 tests.
- Phase 2 (2026-10-16): compact, clear at task end and effort typed into panes with their proofs; movable sections; 108 tests.
- Phase 3 (2026-10-16): autopilot running by itself with its log, tokens per day, Jev port in shadow mode (not connected); 117 tests.
  Owner's choices since the brief: thresholds in `config/thresholds.json` (status set), a stuck bead is a mark
  not a Needs you row, blocker asks show at once, one bead per task session. Deviations from the mockup:
  `REQUIREMENTS.md`, "Phase 1 build notes".

Next:
0. Done (Oct 16): adapters tested against `fixtures/real/`. A derived session name gives way to the pane label;
   an account without a login shows its last good usage, aged, with its status (account 1 `no_credentials`,
   weekly at 100%; account 2 `disabled, relogin_required`); a gate log with no result line reads unknown, not
   red. Still to propose: a Needs you row for an account that needs the owner's login (REQUIREMENTS row first).
1. The owner runs `python3 cockpit.py` on the Mac and does the checks in `RUNNING.md`; answering one ask in the
   embedded grill is the last phase 1 check. Fix whatever differs.
2. Owner undecided: the three model-change marks (Claude Code version and model per session flagged when not
   verified; prices in a config file with their date; self-check of the 33k compaction offset against
   `compact_boundary.preTokens`). Add their rows to REQUIREMENTS.md before building.
3. Phase 2 (controls) needs team dependencies 7 (pause hook) and 8 (launches read team.json); the Haiku
   coordinator window (about 130k) is the first saving to apply through team.json.

Open on the owner's panel when this was written: a5749e (balancer weekly ratios), 44d8ed (finance app; brain
waits on it), ca1d0f (are brain and coordinator exempt from the blocker-wait rule), fc58d4 (accounts 4-17).

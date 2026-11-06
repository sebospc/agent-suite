# What the suite offers

A suite for running a team of long-lived coding agent sessions on one machine. Every part is optional and each
project picks it as is, adapted, or not at all. `parts.json` is the full list with needs, config, install, verify,
uninstall and what leaves the machine; this page says what each part is for. What one project chose is in
`examples/first-project/`.

## 1. Parts

| Part | For | Adapts per project through |
|---|---|---|
| cockpit | One local page: the milestone and its goal metric first, what each session does now, the owner's open asks answered in a grill round, where tokens go, health lights | `.cockpit.json` (paths with `{project}` and `{suite}`, team, port), merged over the user config and checked at start |
| cockpit autopilot | Rules the owner turns on one by one: compact idle sessions over their sweet spot, compact at the next finished turn over the ceiling, keep a cheap-model session under its price step, clear at task end, keep the cache warm across short idle gaps, relaunch a dead session | Rule switches and thresholds in `cockpit/config/thresholds.json` |
| cockpit sweet spot and idle cost | Per session, where compaction costs least, from measured turn sizes, the price card and the cost to rebuild context; each idle gap priced under several policies | Prices, per-role recovery numbers; `cockpit/research/scripts/` to calibrate |
| panel | Every question to the owner on one panel, with options, a recommendation and a why; guards keep asks off chat and the panel file safe | `board_dir` |
| messages | One event, one recipient; real counts in result lines; relays quoted word for word | `docs/PROTOCOL.md` |
| saved-guard | A reply that claims a save or a landing must name it | none |
| receipts | Frozen-patch receipts and a check that the landed commit is the reviewed one | none |
| pause | One file pauses every session | `board_dir` |
| memory | Engram as the team's memory: rules, a save nudge, the after-compaction summary, a migration from markdown files | `engram_project`, `docs/RULES.md` |
| queue | Tickets in flight and next per session; one ticket per session as a hard block; a courier that hands the next one | `courier.*`, `session_prefix` |
| slots | Named resources, one holder at a time with a waiting line | `slots` |
| snapshot | The board, tickets and memory copied to a private repo behind a secret scan | `snapshot.*` |
| team-check | One line per team-order finding, exit 1, so a timer wakes the coordinator only then | `team_check.stale_hours` |
| launcher | Session name from the pane label, the role's launch flags, saved flags on resume | `team.json`, `session_prefix` |
| protocol | Roles, message types, the lead-coordinator flow, review by risk, a prompt template per role | `templates/roles/` |
| rules | Ready-to-paste rule text for every idea in section 2 | `docs/RULES.md` |

Project config for the team tools: `.agent-suite.json` in the project folder (keys in `tools/team/suite_config.py`).
Check an adoption with `python3 tools/doctor.py DIR`.

## 2. gentle-ai ideas and where the suite has them

Each project chooses idea by idea: gentle-ai as it is, the suite's version, or another tool.

| # | Idea | In the suite |
|---|---|---|
| 1 | Memory the agent reaches for first (save, search before asking, summary after compaction) | memory part; `docs/RULES.md` 1 |
| 2 | One recoverable doc per substantial task, the owner's words verbatim | `docs/RULES.md` 2 |
| 3 | Delegate only for a named reason | `docs/RULES.md` 3 |
| 4 | Evidence budget (a quick decision in about 3 calls and 10k tokens) | `docs/RULES.md` 4 |
| 5 | Test first, per rule asked | `docs/RULES.md` 5; receipts part |
| 6 | Receipts on a frozen candidate, depth by risk, one fix round | receipts part; `docs/PROTOCOL.md` "Review by risk"; `docs/RULES.md` 6 |
| 7 | Deterministic next step (a program picks it, not a model) | queue part (task queue and courier); `docs/RULES.md` 7 |
| 8 | Lossless blocking prompts | panel part; `docs/RULES.md` 8 |
| 9 | Skills loaded on match | `docs/RULES.md` 9 |
| 10 | Doctor, deny-list, backups | `tools/doctor.py`; installers back up before writing; `docs/RULES.md` 10 |
| 11 | Four public states (working, checking, ready, needs you) | `docs/RULES.md` 11; the cockpit's session states and needs-you row |
| - | Compaction hook (summary right after compaction) | memory part |
| - | Two layers: rules in the guide plus blocking hooks for rules broken twice | every guard part; `docs/RULES.md` "Two layers" |
| - | Cloud sync off by default | memory part; `tools/doctor.py` flags `ENGRAM_CLOUD_AUTOSYNC` |
| - | One store, topic prefixes per role | `docs/RULES.md` 1, Engram conventions |
| - | Design canvas with comments pinned on an element (Gentle Shell) | not in the suite |

## 3. How the suite uses Engram

- One local store for the team. Every save carries a topic key: `rule/<topic>`, `role/<role>/state`,
  `project/<topic>`, `ref/<topic>`, `archive/role/<role>/state` (`docs/RULES.md` 1).
- Save right after a decision, a fix or a lesson; a role state after each step; a session summary after every
  compaction (the memory part's hook asks for it). Search before acting on a rule you are unsure of.
- A save that may contradict an old one asks for a judgment; each candidate gets a verdict.
- Pinned memories load at every session start, one line each, so the titles must carry the rule.
- Cloud sync stays off; nothing leaves the machine.

## 4. Open

1. Run `tools/check_no_project_names.py` in CI once the repo has CI.
2. The cockpit still names a few first-project facts in its docs (the history of its rules); the code reads every
   project fact from `.cockpit.json`.

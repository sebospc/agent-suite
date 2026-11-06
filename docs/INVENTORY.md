# Agent suite: what it has, what we took from gentle-ai, how we use Engram

Draft, 2026-11-07. A suite for running a team of long-lived coding agent sessions on one machine: one cockpit page, an autopilot that manages tokens, guards on messages and asks, a memory layer, and a config per project. Nothing here names the project it was built on.

## 1. What the suite has today

| Part | What it does | Adapts per project through |
|---|---|---|
| Cockpit page | Current milestone with its goal metric first, what each session does now, the open asks answered in an embedded grill round, where tokens go | `.cockpit.json` (paths, team, port), merged over the user config and checked at start |
| Autopilot | Rules the owner turns on one by one: compact idle sessions over their sweet spot; compact at the next finished turn over the ceiling; keep a cheap-model session under its price step (100k); clear at task end; keep the cache warm across short idle gaps; relaunch a dead session | Rule switches and thresholds in config |
| Sweet spot and compaction model | Per session: where compaction costs least, from measured turn sizes, the price card, cache rebuild cost and the cost to recover context by role | Price table, per-role recovery numbers |
| Idle cost | Prices each idle gap under several policies (today, cap 1, break-even, always compact), so the policy comes from numbers | Policies in config |
| Prices | Reads the provider's price page and flags a change | Price source per provider |
| Metrics and quota | Token use per session and account | None |
| Refit | Learns thresholds back from what happened | Bounds in config |
| Task classifier | Labels a session's task kind, with a shadow mode before it acts | Classifier adapter (real or fake) |
| Controls | Compact, clear, effort, pause the team; each one checks on screen that it took effect | Permission rules |
| Pause switch | One file pauses every session; a guard hook enforces it | Hook wrapped into the project's settings |
| Health lights | Machine (free memory, swap, orphan processes, tool versions), memory store health, docs age | Thresholds in config |
| Installer | `tools/install_project.py` and a setup skill: writes the project config, wraps the status line and the pause guard into the project's settings, keeps a backup, can uninstall | Runs once per project |

Team tools that live in the project today and would move into the suite:

| Tool | What it does |
|---|---|
| Ask panel (`ask_owner.py`, `panel_wait.py`) | Every question to the owner goes on one panel with options, a recommendation and a why; one waiter reports answers |
| Send guard | One event, one recipient; a result line must carry counts; a relay must quote the author word for word |
| Owner-ask guard | Blocks a reply that asks the owner something without a panel ask |
| Memory nudge | Reminds a session to save after 15 minutes without a save; after a compaction it asks for a session summary and a fresh role state |
| Landing receipt (`verify_landing.py`) | A landed commit must match the reviewed frozen patch: tree, message, patch-id, no tool attribution |
| Board snapshot | Copies the task board and memory to a private repo after each push; a secret scan blocks it, with an allowlist of checked false positives |
| Task queue | One file of tickets in flight and the next per session, with device slots granted one at a time |

## 2. gentle-ai ideas: used or not

Each project chooses for itself, idea by idea: gentle-ai as it is, the adapted version described here, or another tool. The suite offers the choice in the project config and never imposes one. The table records what the first project chose.

| # | Idea | Status | How we use it, or what is missing |
|---|---|---|---|
| 1 | Memory the agent reaches for first (save, search before asking, summary after compaction) | Used | Engram, section 3 |
| 2 | One recoverable doc per substantial task, the owner's words verbatim | Partly | The ticket and the decision log carry the owner's words; task messages point to the ticket. No rule yet for a doc per ticket |
| 3 | Delegate only for a named reason | Used | Separate long-lived sessions per role; subagents not used for routine work |
| 4 | Evidence budget (a quick decision in about 3 calls and 10k tokens) | Not yet | Not written as a rule |
| 5 | Test-first per rule asked | Partly | Every logic change leaves one test that fails without it; mutants checked in review. Not written test-first |
| 6 | Receipts on a frozen candidate, depth by risk, one fix round | Used | Frozen read-only patch with hashes and patch-id; review depth by risk (prod code, security, owner quotes); a HOLD gets one fix round; the landing receipt checks the commit |
| 7 | Deterministic next step (a program picks it, not a model) | Not yet | The next ticket is still picked by hand from the queue |
| 8 | Lossless blocking prompts | Used | Panel asks keep every option, label and order |
| 9 | Skills loaded on match | Used | Skills per kind of task; only the matching one enters context |
| 10 | Doctor, deny-list, backups | Partly | Health lights and secret scan; config backups before writes. No single read-only doctor command |
| 11 | Four public states (working, checking, ready, needs you) | Partly | The cockpit shows session states and a needs-you row, not exactly these four |
| - | Compaction hook (summary right after compaction) | Used | The memory nudge on compaction |
| - | Two layers: memory rules plus blocking hooks for rules broken twice | Used | Send guard, owner-ask guard, pause guard |
| - | Cloud sync off by default | Used | Memory store sync is off; nothing leaves the machine |
| - | One store, topic prefixes per role | Used | `role/<role>/state` and `rule/<topic>` keys |
| - | Design canvas with comments pinned on an element (Gentle Shell) | Partly | One typed change under a drawn card; no pinned comments yet |

## 3. How we use Engram

- What: one local store, every session saves with a topic key: `rule/<topic>` for a rule, `role/<role>/state` for where a role stands, `project/...` and `ref/...` for facts.
- When: right after a decision, a fix or a lesson; a role state after each step; a session summary after every compaction (hook). Search before acting on a rule you are unsure of.
- Conflicts: a save that may contradict an old one asks for a judgment; each candidate gets a verdict (related, not a conflict, supersedes).
- Start of session: pinned memories load as context, compacted to one line each so all of them fit.
- Numbers on 2026-11-07: 312 memories (240 rules, 19 project, 17 ref, 14 role, 8 archived), 70 pinned, 13 role states, 13 session summaries, 376 judged relations. In the last 2 days, 12 sessions made 189 searches and 437 saves (most saves come from the one-time migration of the old memory files).
- Gap: searches are still uneven between roles; a few roles rarely search before acting.

## 4. Open before it is a suite

1. Move the team tools of section 1 out of the project into the suite, each behind the project config.
2. Strip every project name from code, docs and fixtures; a check in CI that fails on one.
3. Write ideas 2, 4 and 7 as rules or code, or decide not to.
4. One read-only doctor command over the health lights.

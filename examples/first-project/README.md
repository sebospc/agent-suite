# Example profile: the first project

The suite was built on one project: a team of about ten long-lived Claude Code sessions (lead, coordinator, two
reviewers, workers per platform, design on demand) on one Mac, with beads for tickets, herdr for panes, a panel of
owner asks and Engram for memory. These files are what that project chose. Copy what fits, change the rest.

| File | What |
|---|---|
| `.agent-suite.json` | Team config: board folder, the lead is called `brain`, two device slots, the snapshot remote, every part's choice |
| `.cockpit.json` | Cockpit config with that machine's paths (the suite's own `cockpit/.cockpit.json` is the neutral start) |

## Its choices, idea by idea

| # | Idea | Chose | How it is used there, or what is missing |
|---|---|---|---|
| 1 | Memory first | as-is | Engram, one store; `rule/`, `role/<role>/state`, `project/`, `ref/` keys |
| 2 | One recoverable doc per task | partly | The ticket and the decision log carry the owner's words; no rule yet for a doc per ticket |
| 3 | Delegate only for a named reason | as-is | Separate long-lived sessions per role; subagents not used for routine work |
| 4 | Evidence budget | not yet | Not written as a rule |
| 5 | Test first, per rule | partly | Every logic change leaves one test that fails without it, mutants checked in review; not written test first |
| 6 | Receipts on a frozen candidate | as-is | Frozen read-only patch with hashes and patch-id; review depth by risk; one fix round; the landing receipt |
| 7 | Deterministic next step | partly | The task queue orders tickets; the next one was still picked by hand before the courier |
| 8 | Lossless blocking prompts | as-is | Panel asks keep every option, label and order |
| 9 | Skills loaded on match | as-is | Skills per kind of task |
| 10 | Doctor, deny-list, backups | partly | Health lights and secret scan; config backups before writes |
| 11 | Four public states | partly | The cockpit shows session states and a needs-you row, not exactly these four |
| - | Compaction hook | as-is | The memory nudge on compaction |
| - | Two layers | as-is | Send guard, owner-ask guard, pause guard, saved guard |
| - | Cloud sync off | as-is | Engram sync off |
| - | Design canvas with pinned comments | partly | One typed change under a drawn card; no pinned comments |

## Its Engram numbers, on the day the suite was split out

312 memories (240 rules, 19 project, 17 ref, 14 role, 8 archived), 70 pinned, 13 role states, 13 session summaries,
376 judged relations. In the last 2 days, 12 sessions made 189 searches and 437 saves; most saves came from the
one-time migration of the old memory files (`tools/memory/migrate_md_memory.py`). Searches were uneven between roles:
a few roles rarely searched before acting.

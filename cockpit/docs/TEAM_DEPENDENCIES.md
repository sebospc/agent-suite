# What the team must change for some features

These are changes in the team's own tools (owned by brain), not in the cockpit. Each one unlocks a
part of the cockpit; until it lands the cockpit shows the gap honestly ("no recommendation given",
"decision log not available").

| # | Change | Unlocks | Owner |
|---|---|---|---|
| 1 | DONE (Oct 16): `ask_owner.py add` requires `--rec <option letter>` and `--why "<one paragraph>"`; stored as `rec: {option, why}`, the grill's shape; 3 tests | The grill shows each ask's recommendation | brain |
| 2 | IN PROGRESS, bead pg-81e3: the balancer writes each decision to a JSONL log (time, session, chosen account, score of each account, reason). Sessions may not change `~/.claude`, so brain writes the patch and the owner applies it | "Why the balancer chose" | brain writes, owner applies |
| 3 | DONE (Oct 16): found beads carry a `related` dependency on the done criterion they move; `team_check.py` flags a found bead without one (2 tests). Flagged on purpose: pg-a18q.58 and .59 (move no criterion) | Milestone check 3 | brain |
| 4 | ANSWERED: `claude-cloud` is the assignee label for the owner's cloud chats (the ai chain .64 → .67 → .70 → .74, built and gated, waiting for a reviewer GO). Treat it as a known holder | Milestone check 5 | none |
| 5 | DONE (Oct 16, brain): the fish `claude` wrapper adds `--name old-<role>` from the herdr pane label when the label is one of the ten roles, after the balancer's saved flags; confirmed on agent-ai (saved flags keep the name across a move). brain, coordinator, reviewer and reviewer-2 take it at their next launch; their transcripts already carry the custom-title from earlier renames. shaping-lead added Oct 16 (pane w4:p15 renamed, confirmed on session a764e3ed, panel record 5f1326); its bead assignee is now `agent-shaping-lead` (team_check.py updated; no open bead had the old `shaping-lead`) | Stable session names in transcripts | brain |
| 6 | DECLINED (the owner, 2026-10-16: "No backup"): no board backup; the cockpit's Backup light is gone | | none |
| 7 | The owner said yes (2026-10-16): one switch for brain and the cockpit. A pause hook: while `~/.agent-board/paused` exists, block commit, push and bead claims in every session. The cockpit's button writes it; brain sets it with `python3 ~/Documents/agent-suite/tools/team_pause.py off` (and `on`) whenever the owner says off or on, so the work mode "off" and the cockpit's pause are the same thing | Pause the team: the cockpit's button and the tool are built; the banner shows any commit or claim that got through | brain |
| 8 | Phase 2: launches read `team.json` (model, effort, window per session) and pass `--model`, `--effort`, `--autocompact` | Apply the recommended window; model/effort drift | owner and brain decide |
| 9 | DONE IN THE COCKPIT instead (the owner, 2026-10-16: "se lo dejamos a jev"): at a task end the autopilot clears or compacts as Jev says. No coordinator restart | | none |
| 10 | DECLINED (the owner, 2026-10-16): the balancer takes no task weight | | none |
| 11 | The owner said yes (2026-10-16). The saved guard (`commit_guard.py` Stop hook): stops a reply that says it saved something but names no bead, ask, commit or path that exists, and writes each block as one JSON line `{"t": <epoch>, "session": "old-<role>", "text": "<the reply's line>"}` to `~/.agent-board/saved_guard.jsonl` | Said vs saved shows the blocks | brain |

## Prompt for brain (open items 7 and 11, 2026-10-16)

Paste into brain's pane:

```
brain: the owner decided (2026-10-16, cockpit docs/BRIEF.md): two team-side changes, cockpit docs/TEAM_DEPENDENCIES.md 7 and 11.
7  One off switch: when the owner says off (or on), run python3 ~/Documents/agent-suite/tools/team_pause.py off
   (or on); the team is off now, so run it once today. Then a pause hook: while ~/.agent-board/paused exists,
   block git commit, git push and bd claims (bd update --claim, status in_progress) in every session (PreToolUse
   hook), and log each block. The cockpit's Pause button writes and removes the same file.
11 Saved guard (commit_guard.py Stop hook): stop a reply that says it saved or recorded something but names no bead,
   ask, commit or path that exists; write each block as one JSON line {"t": <epoch>, "session": "old-<role>",
   "text": "<the line>"} to ~/.agent-board/saved_guard.jsonl.
Not wanted any more: the board backup (6), the coordinator's 120k restart (9; the cockpit's autopilot clears or
compacts at a task end as Jev says), a task weight for the balancer (10).
Reply with the bead id for each, or why not.
```

Already decided with brain in the same conversation (beads exist on the board):
- `pg-15yj` tools/go_req.py, script-written GO-REQ receipts.
- `pg-208g` send guard: one event to one recipient (keyed on sender + line 1, sent log outside the
  session, fails open).
- `pg-5zn3` `category:` line on HOLDs and a weekly count by message type.
- `pg-f8q9` a second HOLD on the same finding goes to brain for a ruling.
- `pg-i652` HOLD probes become matcher regression rows.
- Ask 8779c2 answered A: one review depth for every change.

Proposed to brain, status unknown when this repo was written: a `commit_guard.py` Stop hook (a reply
that says it saved or opened something must name an id that exists), and recording every decision
the owner gives in chat on the panel in the same turn.

## Board state after brain's fixes (Oct 16)

- pg-67gb.1 and pg-67gb.3 (M5) are back to open with a note; when the team resumes, .3 goes first
  (owner's answer 2fdc3a ties the build-model switch to it).
- pg-a18q.53 did not move for 12 h because the team is paused; it is landed and waits for the next eval.
- pg-a18q.30 (approve your finance app) is blocked with blocker ask 44d8ed; brain recommends B (one
  more grill round), because Improve (.35) is not on the owner's phone yet.
- pg-a18q.51, .68 and pg-fsto had answered asks (b377fa, 6 asks, d815d5) but were still blocked; set
  back to open.
- team_check.py shows no blocked bead without an ask.
- `ask_owner.py` and `team_check.py` are not in git (backups `.bak-rec`, `.bak-criterion` in
  `~/.agent-board`). The board backup (dependency 6) should cover the board scripts too.
- Owner panel records: 565465 (create this repo), 8894de (this list).

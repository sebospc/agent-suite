# The milestone view

The owner's first must have. It answers three questions, in this order:
1. Is the milestone's goal moving? (the result, never a count of tasks)
2. What is left, who has it, and what does it wait on?
3. Is the team working on it, and is it in order?

## Where the data is

| Thing | Source |
|---|---|
| Milestones | beads with `issue_type: milestone`, title "Mn: …". Current one: the open milestone with the lowest n (Oct 15: `pg-a18q`, M4) |
| Children | beads with a `parent-child` dependency on the milestone (`dependencies[].type == "parent-child"`, `depends_on_id` = milestone). Walk it recursively: `pg-a18q.50.1` is under `pg-a18q.50` |
| Done criteria | `~/.agent-board/dod.json` → `milestones.<id>.dod` (list of bead ids), plus `changes` (dated, with the owner's words) and `bar` |
| Found work | children labeled `nice` (not done criteria); `from:Mn` label when moved from another milestone |
| Goal metric | `~/.agent-board/goal.json`: `{"label","value","total","target","source"}` |
| Priority rule | DECISIONS 2026-10-13: P0 is worked at once outside milestones; P1 is `nice` in the current milestone; P2-P4 go to the next milestone |
| Asks | `~/.agent-board/panel.json` → `asks[]` (`id`, `text`, `options`, `kind`, `by`, `asked`, `bead`, `coverage`) and `answered[]` |
| Session list | herdr panes (see `DATA_SOURCES.md`) and the team table in the project repo `docs/WORKFLOW.md` |

`reference/panel/team-roadmap/roadmap.py` is the panel's current logic: reuse its rules (done
criteria, nice, from: labels), drop its percent bar.

## 1. The goal first

Show `goal.json` as a sentence: "6 of 10 apps fully right. Now 2 of 10." with its source line
("weekly eval 4, majority of 3 samples, Oct 14, 6ca48b2e") and the next eval date if known.

Then the done criteria as a count and as one small cell per criterion, in `dod.json` order:
filled closed, half in progress, amber outline blocked, empty open; the criterion that IS the goal
ringed (`bar` in dod.json, or the criterion whose title names the goal). Never a percent bar: on
Oct 15 the bar read 85% (22 of 26) while the goal criterion itself (6/10) stood at 2.

## 2. What is left

One row per open done criterion: id, title, holder, state, last update, and what it waits on:
- in progress: "moved <time>"
- open with no linked work in progress: amber, "no bead in progress is linked to it"
- waiting on the owner (assignee `owner`, or a title or label that says the owner approves): amber
  if no open ask has `bead` = this id
- blocked: amber if no open ask names it

Below: found work counts (closed, in progress, open, blocked), stated as never counting toward the
criteria.

## 3. "Is the team on Mn?" (seven checks, each pass or fail with its evidence)

Replaced on 2026-10-16 (the owner): the section and its "Show the N that pass" link are gone. Checks 1, 2, 6 and 7
already show elsewhere (work off the milestone is a Needs you row; a criterion nobody moves is amber on its tile; a
stuck bead has its mark; main green is the Main light). Checks 3, 4 and 5 are one Needs you row, "Team rules broken:
... [Tell brain]", shown only when one breaks (`cockpit/milestone/team_rules.py`). The rules below still define how
each one is computed.

Sessions that coordinate or review (brain, coordinator, reviewer, reviewer-2) are expected to hold
no bead; exclude them from the "one bead" checks. `claude-cloud` is the label for the owner's cloud
chats: a known holder, not a team session, and allowed to hold a chain of beads.

The Oct 15 results below are the snapshot that motivated the checks; brain fixed most of them on
Oct 16 (`TEAM_DEPENDENCIES.md`, "Board state after brain's fixes"). A paused team (owner's word)
explains silence: check 6 should not fire while the team is paused.

| # | Rule | How to compute | Oct 15 23:05 result |
|---|---|---|---|
| 1 | Work in progress belongs to the milestone, or is P0 | every `in_progress` bead: under the milestone (recursive parent-child) or `priority == 0` | Fail: 8 of 10 in M4; `pg-67gb.3` (P1) and `pg-67gb.1` (P2) are M5, held by agent-ai |
| 2 | Someone moves each open done criterion, or an ask waits on the owner for it | for each open criterion: an in-progress bead linked to it (see check 3), or it is itself in progress, or an open ask with `bead` = it | Fail: `pg-a18q.29` (the 6/10 goal) has nothing; `pg-a18q.30` (owner approves finance app) and `pg-a18q.51` (blocked) have no ask |
| 3 | Found work names the criterion it moves | every in-progress `nice` bead has a `related` dependency on a done criterion (team convention since Oct 16; team_check.py flags the rest) | Fail: 0 of 7 |
| 4 | Each session that does task work holds one bead | count `in_progress` per assignee, excluding coordinating and reviewing sessions | Fail: agent-ai 3, agent-ios 2, claude-cloud 2 |
| 5 | Every bead holder is a team session | assignee in the session list (plus `owner` and `claude-cloud`) | Fail: `claude-cloud` holds 2 in progress and 5 open |
| 6 | No bead in progress goes 6 h without an update | `now - updated_at > 6 h` for `in_progress` | Fail: `pg-a18q.53` (agent-ai), 12 h |
| 7 | Main is green and nothing waits to be pushed | last `verify_commit.sh` result on the landing ref; `git rev-list origin/main..stack-brain` | Pass |

Show the summary as "6 of 7 checks fail", each with its evidence and source. These are facts from
the board, not a score. The 6 h and "one bead" thresholds are starting values: confirm them with
the owner.

## Per session: "Working on"

In the sessions table, each session shows its in-progress bead(s) and the kind: M4 done criterion,
M4 found work, M5 (or another milestone), P0, "no bead" (idle with ready beads is flagged), or
"coordinates / reviews, holds no bead". The selected session's panel spells it out in one sentence.

## Later, once the cockpit keeps history (phase 2)

The collector snapshots every 30 s. From the history: share of each session's tokens spent while it
held a milestone bead vs off-milestone work, per day; time from claim to close per bead. These are
the trend lines that prove the team works on the milestone over time.

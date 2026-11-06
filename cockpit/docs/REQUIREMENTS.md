# Requirements

Every element below has a purpose: the decision it changes, or the trust it gives. Adding an
element means adding its row here first. Values on screen always show their source and age, and
whether they are measured or a heuristic.

## Principles

- Dark cockpit: nothing is lit when everything is normal. Only what needs the owner stands out
  (caution amber, warning coral), and it carries its action inline.
- Two tiers of abnormal: "Needs you" (the owner can act) and "Handled by itself" (abnormal, but the
  autopilot or balancer deals with it). Normal items collapse into one "Clear" line.
- No progress bar that is not a measured result against its target.

## Screen elements

### Header
| Element | Purpose | Source |
|---|---|---|
| Read time, refresh period, refresh line | Trust: how fresh every number is, and that the cockpit is still reading | collector |
| Pause the team / Resume (the owner, 2026-10-16: "Yes"); a paused banner under the header: since when, and the commits and bead claims made after it (none while the hook holds) | Stop all commits, pushes and bead claims at once, and prove nothing got in | `~/.agent-beads/paused` (exists while paused, holds the epoch; brain's hook reads it, TEAM_DEPENDENCIES 7), git log, bd (started_at) |
| "Prices differ from Anthropic's page (N)" (amber, opens the list), only when the daily price check finds a difference | Trust: the sweet spot minimises dollars per turn with config/prices.json, so a stale price is named where it is seen first | price check job |

### Layout (the owner, 2026-10-16: one screen, compact, ordered and usable)
Header line, the lights strip, then two columns that each scroll by themselves: Needs you, Your
asks and the milestone on the left; sessions, tokens, accounts and background jobs on the right. Below 1100 px wide it is one column and the page scrolls. Every section has the same
shape: a header that opens and closes it (remembered in the browser), then one-line rows in fixed
columns; clicking a row opens its full text, source and controls under it. Long text lives only
in those details.

| Element | Purpose | Source |
|---|---|---|
| Sections that open and close | The owner keeps open what they watch; everything fits one screen | the page |
| Sections that move (drag the grip, or arrow keys on it), kept per browser; the milestone first by default | The owner puts what matters most to them first (the owner, 2026-10-16: "que los paneles sean movibles ... el del milestone para mí es el más importante y debe ir de primero") | the page |
| One-line rows that open their detail | Many items in little space, every explanation one click away | the page |
| Header "N sources unavailable" (opens the list) | Trust: a missing number is named, without a line of errors on screen | collector |
| Needs you shows at most 5 rows, "Show N more" for the rest | The worst rows first, the list stays short | rules below |
| A "Log (N)" line at the bottom of Sessions, Your asks, the milestone and Background jobs, closed by default, opening in place (the owner, 2026-10-16) | Trust: what already happened in that section, one click away, without filling the screen | each section's own log (below) |

### Team health (grill round with the owner, 2026-10-16)
A section like the others, first in the right column by default. One row per resource, its main number and its level
(OK, WATCH, ACT); a row opens its detail in place. It only informs: what needs the owner is in Your tasks.

| Area | Purpose | Source |
|---|---|---|
| Tokens | Where the tokens go, today without cache (input + output, the owner 56fba6); its detail is the former Tokens section (per day with and without cache, per session, per landed bead, messages) | transcripts |
| Context | Sessions over their sweet spot, each with its context and spot | transcripts, cost model |
| Autopilot (the owner, 2026-10-16: "debe afectar algo en el team health") | Whether it runs and its actions took: WATCH when stopped in config/thresholds.json or an action today failed or went unproved; its value is the context it cut today, or "paused" | actions.jsonl, thresholds.json |
| Memory | Start loads against each role's usual; an idle session whose notes were not saved during its last turn (see "Notes saved" below) | transcripts, bd, role state files |
| Said vs saved | What was said against what lasts; its detail is the former Said vs saved section | panel.json, the decision log, bd, git, transcripts, saved guard |
| Disk | Free space against the team's 30 GB floor; the transcripts, board and cockpit folders | disk usage |
| Coordination | Review receipts, duplicates, messages outside the format, team rules | transcripts, bd |
| Code | Main green or red, commits to push | gate logs, git |
| rtk, caveman, ponytail, context-mode, i-have-adhd (the owner, ask 8ccee2: "ver que todo está siendo efectivo o no"; i-have-adhd, owner 2ae134) | One row per token tool, to keep or drop it: the sessions where it is on (rtk and context-mode: their hook ran in 24 h; caveman and ponytail: the session's settings layers enable the plugin, pg-qbw3, since a session older than a day ran no SessionStart; i-have-adhd: "ADHD MODE ACTIVE" at its last start), its own count (rtk's saved tokens today; context-mode's bytes kept out / 4, heuristic; caveman and ponytail count nothing), tokens per finished task (bd close) and re-reads with it on and off, median output per turn for caveman and ponytail; WATCH when its hook crashed or timed out, or its sessions spend more per finished task | rtk gain, context-mode session databases, transcripts |
| Handled by itself / Clear (two lines at its bottom) | Abnormal but handled, and what is clear | as below |

The top band of lights is gone (the owner: "is useless").

Each area's detail is a table (the owner, ask 834b86, bead pg-bo7k: "no quiero mucho texto, solo datos, dinamicos,
especialmente tabla, lo que quiero es que todo se pueda medir y quede registrado, especialmente lo relacionado a tokens"):

| Element | Purpose | Source |
|---|---|---|
| One table per area, one row per session, tool or measure, numeric columns, sorted by a click on a column head; a one-line caption, the area's own figures (totals) above it, and one line saying why when it is WATCH or ACT | The owner reads numbers, not prose, and sorts by what matters to the decision at hand | the area's own source, named under the table |
| Tokens table, first: per session, account, model, input, output, cache read, cache write, cache hit (cache reads over input, cache writes and reads, measured; the team figure in the totals), context, cost, tokens per finished task, no cache, with cache, last hour, share, share above its sweet spot (~), start load (~); "Idle cost ~" per session; totals 24 h without and with cache, today, the 6-day average, 24 h cost, 24 h idle cost (~). Every token figure but the cache columns and "with cache" is without cache: fresh input and output (the owner, 56fba6) | Where the money goes, split so cache reads (cheap) and fresh input and writes (dear) are not mixed; cost lets a session be compared in dollars; idle cost is what the session's idle gaps over its cache life cost today, in cache rewrites and idle compactions, the baseline the keep-warm probe (mb-s347) is weighed against | transcripts, deduped; cost at list price from config/prices.json, each request on its model's card; cache writes at the tier of the session's current TTL (~, the tier is not logged); unknown, not partial, when a model has no card; idle cost from transcripts (gaps over the cache life, a compact_boundary inside a gap marks an idle compaction) at the session's price card and sweet spot, ~ heuristic, unknown without a card or a sweet spot |
| Per landed bead and HOLD rate by context, as two more tables under Tokens | Same purpose as in the Tokens section below, as data | as below |
| Tool tables (rtk, caveman, ponytail, context-mode): per session on or off, tasks closed, tokens per task, re-reads, hook failures, context-mode's kept out (~); totals: its own count, per task on and off, sessions on | Whether each tool pays: per task on against per task off | as in the area row |
| `~/.agent-cockpit/metrics.jsonl`: one line per read, holding every table row that changed since the line before (a gone row as null, totals under `_totals`); the first line of a run holds every row | Every number on these tables has its history, so a trend is measured instead of remembered | the tables themselves |
| Autopilot's task-end clears table: per session its clears and wrong clears in 7 days and whether it gets only compact; "Wrong clears, 7 d" in its totals | Whether clearing at a task end loses work the next task needs (the owner, 4f79d1: "keeps related work") | actions.jsonl `cleared` and `wrong_clear` records |
| A number in a table opens its history: a step line since its first value in 24 h, with low, high, now and how many changes | Whether a measure moves after a change (a tool turned on, the autopilot, a compaction) | metrics.jsonl through `/api/history?area=&row=&key=&hours=` |

The former per-session prose details (who started its turns, the start-load sentence, the messages line) are gone
from Team health: the numbers are in the tables, the messages line is the Coordination table.

### Your tasks: Actions (formerly Needs you; actionable abnormal items, sorted warning first)
Each row: level word and icon, one sentence, its source line, one action button. Rules that light a row:

| Light | Rule | Action | Source |
|---|---|---|---|
| Haiku session above 100k | context > 100k on Haiku 5.5 (5x price step) | Compact <session> | transcript |
| Work off the milestone | in-progress bead not under the current milestone and not P0 | Tell the coordinator | bd |
| Owner's criterion without an ask | open done criterion waiting on the owner, no ask | Add it to my asks | bd, panel.json |
| Silent bead | in progress, no update for 6 h | Ask <session> | bd |
| Main is red (warning) | the last gate failed: names its commit and failing count | Tell brain | gate log |
| Review receipts do not match (warning) | this week a GO or HOLD names a sha256 no GO-REQ for that bead sent, a LAND-READY one no GO approved, a LANDED came with no GO, or a GO-REQ, GO, HOLD or LAND-READY names no sha256 (the owner: "cada review tiene un hash") | Tell the coordinator | messages between sessions, their `sha256:` line |
| A Haiku session that cannot stay under 100k (warning) | its base (first turn's context, or its last compaction's size) is at the Haiku guard or above: compacting cannot help, so the autopilot stops compacting it | See sessions | transcript |
| Missing id (a row per session for ids that do not exist, and another for "saved" with no id) | a reply today names a bead (`pg-…`), an ask (`ask <6 hex>`) or a commit (`commit <sha>`) that does not exist, or says saved or recorded with no id at all. Each row names the id or the saved claim, the line of the reply it came from and its time. Only the session's own words count: fenced code, `>` quotes and text in double quotes are skipped; a file name (`team.json`) is an id for a saved claim; an ask or commit id needs a digit (the words decade, facade and defaced are not ids) | Ask brain to check it | transcripts, bd, panel.json, `git cat-file` in each repo of `.cockpit.json paths` `repos`, in order (projectapp, agent-cockpit, ~/.agent-beads): a sha found in any of them exists |
| Team rules broken (one row, only when one breaks) | found work in progress links no done criterion; a session that does task work holds more beads than its limit; an open bead's holder is not a team session, with its stuck beads named (it has no session row to carry the mark) | Tell brain (copies a prompt naming each break) | bd, team_sessions.json, thresholds |
| Account needs your login | cswap `usageStatus` `no_credentials` or `relogin_required`, or `disabled`, and a live session or the balancer's next pick is on it (otherwise one line under Handled by itself) | Copy `cswap-relogin <slot>`; when the account is `active: true` (logged in on `~/.claude`) the row says to tell brain instead | cswap list --json, cswap session files, balancer log |
| Token tool config changed (warning) | a line naming rtk, caveman, ponytail or context-mode was added or removed in a watched settings or `.mcp.json` file since the cockpit's baseline (the owner, ask 8ccee2: "por si daña la config de alguna agente"); deleting `~/.agent-cockpit/config-baseline.json` accepts the new config | Tell brain (the diff per file) | `guarded_configs` in .cockpit.json paths, the baseline |
| Token tool hook failed (caution) | a token tool's hook crashed or timed out in a live session in 24 h | Tell brain (session, tool, what it said) | transcripts (hook errors) |

A button whose text goes to a team session types it into that session's pane on the owner's click (design chat N8,
N11): the page names the row, and the server types the core's own text, so no other page can type through it. Its
proof is that session's next turn. A row the owner acted on stays, dimmed, with "Sent", "Done" or "Copied HH:MM" and
its result in place of its source, until the next read drops it (N5). Commands for a terminal (`cswap-relogin`) are
still copied.

Needs you holds only actions; a blocker ask is shown only in Your asks, and the Asks light goes ACT for it (the
owner, 2026-10-16: "a blocker ask appears only in Your asks, and Needs you holds only actions").

Grouped (the owner, 2026-10-16): done criteria that wait on the owner without an ask are one row. Jump actions name
the tab they open.

Removed (panel 7671bc, 2026-10-22): the "over sweet spot" row (the autopilot compacts those sessions; the Sessions tab
still shows each one), the "Wake <session>" row (the nudger outside the cockpit prompts idle sessions with work) and the
"project settings file overrides the autopilot" row (the autopilot no longer decides model, effort or plugins).

### Model-change marks (the owner, 2026-10-16; thresholds provisional)
| Mark | Rule | Where | Source |
|---|---|---|---|
| C: compaction off its expected point | an automatic compaction's `compact_boundary.preTokens` differs from the expected window minus 33k by more than 5k (expected window: team.json, else the model's window in `config/prices.json`) | the session's row and panel | transcript, team.json, prices.json |
| B: price card stale or missing | `config/prices.json` `as_of` older than 90 days, or the session's model has no price | the session's row and panel; the Sessions tab line | prices.json |
| A: Claude Code version or model not verified | waits | | |

### Handled by itself / Clear (one line each)
Busy sessions over their sweet spot (autopilot compacts when the turn ends); an account at 85% of its 5h window (balancer keeps cold and new sessions off it). Clear: main
green, tokens today vs yesterday, no duplicate message today, no message outside the format this week. Duplicates
light up the Duplicates light instead (nothing handles them until the send guard pg-208g is built).

### Milestone
See `MILESTONE.md` for the goal and criteria. Shown visually, few words (the owner,
2026-10-16: "muy visual, lindo, animaciones, no tanto palabras, pero que represente la realidad"):

| Element | Purpose | Source |
|---|---|---|
| The milestone's subline under its heading: id, when its done criteria were set, who approved them | Trust: the criteria are the owner's, not the team's | dod.json |
| Road of milestones (a ring per milestone not closed yet, filled with its closed criteria; the current one marked) | Where the team is in the rest of the plan, and what comes next (the owner, 2026-10-16: "shows only milestones that are not closed") | bd milestones, dod.json |
| Goal, done criteria, closed per day over 14 days | Whether the milestone really moves | goal.json, bd (closed_at) |
| Goal's target date and next eval, only when goal.json has `target_date` and `next_eval` | When the goal is judged next; never worked out by the cockpit | goal.json |
| Done criteria legend and "N of M closed. The K left include the goal itself." | The cells read without guessing | dod.json, bd |
| Open criteria as tiles, with the sessions moving each one on it (a busy session's dot breathes), its holder and last update age | Whether the agents work on the milestone right now, and which criterion nobody moves | bd, herdr state |
| Log (N): beads under the milestone closed in the last 7 days, newest first, each with the session that held it | What the bars of closed per day are made of | bd (closed_at) |
| Any bead id opens its card (description, notes, links, comments) | The owner reads a bead without a terminal | the last bd export |

### Motion (`DESIGN.md`, Motion)
| Element | Purpose | Source |
|---|---|---|
| Working glyph and sweep on busy sessions | See who works and who sits idle at a glance | herdr state |
| Warning blink until acted on | A warning is noticed even when the owner only glances | the Needs you rules |
| Breathing in-progress criterion cell | Which criterion someone is moving right now | bd |
| Context bar shrinks after a compaction | Proof the compaction happened, seen, not only read | compact_boundary record |

### Sessions table
| Column | Purpose | Source |
|---|---|---|
| Session (select) | Opens the session panel | herdr pane list |
| Start / limit (bar, orange over its limit; tick at the limit) | What the session loads before any work (CLAUDE.md, system prompt, tools, memory) against its role's usual over 14 days plus `start_load_rise_pct` (20%, provisional) (the owner, 2026-10-16); the files it loads were dropped (the owner, 2026-10-17, panel d00915) | transcripts: first request minus the message that started it (~) |
| State busy / idle / off, with the working glyph and sweep | Who can be compacted now; who is stuck; who is working, seen without reading | herdr, process table |
| Account, in the Session cell after the name (owner 2026-10-19, pg-i0zr: no column of its own) | Why its quota moves | the process's own `CLAUDE_CONFIG_DIR` (`ps eww`, only that variable kept); every profile's `sessions/` can be one shared folder, so the folder cannot tell (brain's report F15) |
| A side project's session (`.cockpit.json` `team.projects`: role to working folder; now `agent-ddp`, the owner via brain, 2026-10-22: "mete al agent-ddp alc ockpit para calibrarlo tambien como los otros agentes") | It gets a row, metrics, calibration, keep-warm and the autopilot like a agent-<role>, though it was launched with no `--name`; a role that holds no bead (listed in `coordinating`) | the live record's `cwd` (read only) against `projects`; the transcripts are already read for every folder under `~/.claude/projects` |
| Model, effort; drift vs team.json (amber "≠ team.json" in the cell) | Catch a session running something other than intended | transcript (model), status line or pane (effort), team.json |
| Context and sweet spot (bar + tick); after a compaction that recorded no size, "compacted HH:MM, size on its next turn" instead of 0 or the old size (brain's report) | Who is wasting tokens | transcript, compaction model |
| Working on (bead + kind tag: criterion, found, P0, next M, off, role, idle) | What each agent is doing, and whether it is milestone work | bd |
| Plugins and Skills, in each session's detail only (owner a4e769, pg-qbw3; out of the table, owner a16693, pg-uz7w): the plugins it really loads, enabledPlugins merged over user (the account's settings, a link to `~/.claude/settings.json`), project, local and its `--settings` file, later layers winning, plus each `--plugin-dir`, plus each mode its last start's SessionStart hooks switched on that no loaded plugin explains, marked "(SessionStart hook)" (brain's i-have-adhd, pg-g22n); start modes count only from a SessionStart record after its process started (the live record's `startedAt`), else it says none was seen since; the skills it invoked; its detail adds the modes its last start's SessionStart hooks switched on and its launch flags | Whether a session runs the tools the owner set for it (brain: i-have-adhd, no caveman) | settings files, herdr's argv of its process (`ps` only `--settings` and `--plugin-dir` when herdr has none, never the environment), transcripts |

| Log (N): the owner's controls sent today, each with its proved result | Trust: what the owner's clicks did, after a restart too | `~/.agent-cockpit/actions.jsonl` |

Removed: messages per session (no decision hangs on it). Tokens 24 h and tokens per day moved to Tokens (the owner,
2026-10-16: Sessions keeps state, context and work).

### Tokens (the owner, 2026-10-16: "deberíamos tener una sección dedicada a tokens")
| Element | Purpose | Source |
|---|---|---|
| Header: the team's last 24 h; summary today and the 6-day average (amber when today is over it) | Whether today runs hot | transcripts, deduped |
| Per day, 7 days, today so far last, bars without cache (input + output, the owner 56fba6), with cache in the tip (the owner, 2026-10-16: "quiero que haya sin cache y con cache"); hovering or focusing a bar shows its day and both figures; the same pair for each session and the header | Cache reads are most of the volume but cost a twentieth of fresh input on Opus 5.5, so the two together say what is volume and what is spend, and whether compaction and the autopilot bring it down | transcripts |
| One row per session that spent in 24 h, most first: bar, tokens, share of the team, share spent above its sweet spot | Who spends, and how much of it is avoidable context | transcripts (by session name, subagents included), sweet spot |
| A row's detail: last hour, cached / fresh / output split, who started its turns (another session, you, a control, its own work) | Why a session spends: re-reads, writes, or being woken (design chat S10, LI14) | transcripts: the user line that opened each turn |
| Start load per session (its first turn: CLAUDE.md, system prompt, tools, memory) and its share of an average turn, amber at `start_load_share_pct` (40%, provisional); a team line with the median and the largest (the owner, 2026-10-16: "cuanto está consumiendo el claude.md ... para saber si estamos bien o mal con la carga inicial") | Whether what a session loads before any work is too big, since every turn re-reads it | transcripts: the first request of the current session |
| High context line: share of the team's 24 h above `high_context_tokens` (150k, provisional) | The measured lever (measured on the first project: about 70% of use ran above 150k) | transcripts |
| HOLD rate by context band (owner decision 767efc, bead pg-yn73): per model, for the sender's context when it sent each GO-REQ: under 100k, 100-200k, 200-300k, over 300k; each band shows its HOLDs out of n reviews; a band under `hold_band_min_reviews` (10, provisional) reads "not enough data" | Whether review quality drops as context grows, and the data that sets `quality_cap_tokens` (today null: no cap) | transcripts, measured. A review is a GO-REQ (sender, time, bead, sha256) whose verdict is the first GO or HOLD naming the same bead and sha256 after it (HOLD if any HOLD, else GO; no verdict yet is left out); the sender's context is the size of the request that sent it (its own transcript); the model is that request's. A patch sent twice counts once, at its first send |
| Per landed bead, by session: tokens per bead closed this week against last week, "rising" when over by `tokens_per_bead_rise_pct` (20%, provisional) | Whether a session gets more expensive per finished task (design chat LI13) | bd (started_at, closed_at, assignee), transcripts; heuristic: a session's tokens in the bead's window |
| Messages this week (one line): messages per bead median and worst 10% against last week, duplicates (target 0) and their turns' tokens, messages outside the WORKFLOW format (target 0), beads with 2 HOLDs or more | Every message wakes a full turn (projectapp WORKFLOW "Messages"), so coordination is a token cost (design chat LI15, LI16) | transcripts: `<cross-session-message>` lines, line 1 `<TYPE> <bead> [vN]` |

### Session panel (selected session)
Context vs its sweet spot with the reason in one sentence; its age (turns and hours since its fresh start) and today's
compactions with before and after (design chat S11); controls ("Compact <session>", clear, effort); "How the sweet spot
is worked out" collapsed (formula and inputs), and it stays open across reads until clicked again. A busy session's
reason says the autopilot compacts it once idle. Taken out (the owner a4e769, pg-0mat): the "Holds ..." line (Working
on says it), the compaction drift line, Jev's four scores, the effort and model cache line and the notes-not-saved
explanation (the button is off and says why on hover).

| Element | Purpose | Source |
|---|---|---|
| In "How the sweet spot is worked out": the session's task kind (the bead's labels, else Jev's category for the bead, else "no bead") and its measured recovery cost per compaction, in tokens and list dollars, with how many compactions it is the mean of; "fleet value, provisional" when its kind has fewer than `recovery_min_compactions` | A task that compacts expensively gets a bigger sweet spot, and the owner sees why: the cost a compaction adds (re-reading what the summary dropped) is measured, not assumed 0 as the re-read heuristic left it (CALIBRATION.md: k_R and D at 0) | transcripts (compact_boundary, then each request's usage and tools), bd (who held which bead when), Jev (category of an unlabeled bead) |
| Thrash guard (COMPACTION.md rule 8): when a session's last two compactions both left it at or above the line the autopilot compacts at (its first request after each one), the autopilot stops compacting it; its skip reason says so and asks to raise its window or clear it | A compaction that refills at once costs a compaction and frees nothing; repeating it is the thrash Claude Code itself stops after 3 | transcripts (compact_boundary, the first request after it) |

### Said vs saved (design chat N18, N20)
| Element | Purpose | Source |
|---|---|---|
| Your answers today, and those not in the decision log yet (as committed on the landing ref) | Trust: what the owner decided is written where it lasts | panel.json answered, `git show <landing ref>:docs/DECISIONS.md` |
| Beads opened today; commits on the landing ref today | What was saved today, with ids | bd (created_at), `git log --since` |
| Replies that said saved or recorded with no id (a file name, a path, a bead, an ask or a commit counts as an id; a quoted "saved" is not the session's claim); the row shows the line, per session; where replies said they saved (scratchpad, agent memory, a file) with how far each is trusted | The owner: if it has no id it does not exist; a scratchpad is not trusted, an agent's memory file only for that agent | transcript replies of 24 h |
| The saved guard's blocks | Waits on the guard's log (TEAM_DEPENDENCIES 11) | |

Every region names the read its numbers come from ("Read at HH:MM:SS"), and marks heuristic numbers with "~" (the
sweet spot, the share above it, tokens per landed bead) beside measured ones (context, tokens, account use)
(design chat D11, D12). A live session with no transcript says it may have been launched without `--share-history`
(D15); a transcript with no custom title takes its AI title.

### Your tasks (the owner, 2026-10-16: "your tasks ... separacion de preguntas y de tickets"; no embedded grill)
Two groups: Questions (panel asks, answerable here) and Tickets (beads on the owner that are not questions: assigned to
the owner, parked items included, or done criteria waiting for approval with no ask; each says why it is the owner's).
| Element | Purpose | Source |
|---|---|---|
| One row per open ask, opening to its text, context, recommendation, its options as buttons and a box for the owner's own words; a click stages the answer (see the staged bar) | Answer one question without a round | panel.json |
| Staged bar under the header: answers and Actions/Sessions controls staged by click (a second click takes one back), "Confirm and send N" sends all in one POST `/api/batch` in the order staged, Discard drops them; a failed one stays staged with its reason. Copy, jump, Pause and the grill round stay instant (the owner, 2026-10-17, panel d00915) | The owner reviews everything before anything is typed or saved, and sends it in one go | the same handlers as a single click |
| A tick on each ask and "Open a grill round for N ticked": grill-with-ui in its own tab, blocking or not | A round for the questions the owner picks | grill-with-ui |
| A comment in a grill thread is typed into the pane of the session that asked; the thread says it was sent | The owner can discuss before answering | herdr, actions.jsonl |
| Beads that wait on the owner without an ask, marked ○ | Brain writes their question (the owner, 2026-10-16) | bd |
| Log (N): the answers saved today, each with its time and the owner's words, wherever they were given | Trust | panel.json `answered[]` |

### Accounts
Per account: 5h and 7d use with reset times and the 85% tick, sessions on it. See `BALANCER.md`. The balancer's
choices moved to Background jobs, with the autopilot's, in one log.

### Background jobs (replaces the Autopilot block; the owner, 2026-10-16: "se supone que esos son jobs que ocurren en segundo plano ... puedo interactuar con ellos?")
One line per process that runs by itself: its name, what it does in a few words, when it last acted, what it did.
No switches and no long text; the row's detail holds the exact rule and the sessions it left alone, with the reason.

| Job | Purpose | Source |
|---|---|---|
| Next run, on every job and hook (the owner, 2026-10-16: "a cron column ... when is going to be executed") | When each job runs again: the next read's time, the price check's next day, the balancer on a session start or move, each hook on its event | collector, price check, settings |
| Autopilot, one row like the others (the owner, 2026-10-16: "el autopilot es super importante ... deberia mostrarse claramente como un job como los demas") | Trust: whether it is on, its latest action, today's proved compactions and the context they cut, what waits for its proof and what was not proved; replaces the "Today the autopilot cut" footer | actions.jsonl |
| Each autopilot rule, named "Autopilot: <rule>" | Trust: it runs, what it compacted, and why it left a session over its spot alone (busy, notes not saved, idle less than its wait, a control still waiting) | actions.jsonl, the rules on each read |
| Compacted by itself, on the Autopilot row and in the jobs log (brain's pg-efsm) | Trust: a session Claude Code compacted on its own trigger today, before the sweet-spot rule did, with its before and after; each one is a miss of that rule | each session's transcript, `compact_boundary` with trigger auto |
| A pane that refuses the autopilot's text, as a reason under its rule and an `actions.jsonl` "refused" line, with when it is tried again (brain's report F10: herdr did not list the coordinator as an agent, so every send failed where only the console saw it) | Trust: why a session the rules picked was not compacted | herdr agent prompt result |
| Balancer | Its last choice of account | the balancer's decision log (pg-81e3) |
| Read every 30 s | Trust: the page is fresh, and how many sources failed | collector |
| Price check, daily | Trust: config/prices.json still matches Anthropic's prices page (the owner: "deberiamos tener un cronjob revisando los prices") | platform.claude.com pricing page (`.cockpit.json paths` prices_page), prices.json |
| Jev record | Trust in Jev: each bead's suggestion beside what ran and how it ended, by class, until it can be judged | `~/.agent-cockpit/jev_record.jsonl` |
| Hooks (one line per script, read only; the owner: "only view and logs"): its script, every event it runs on, what its log says it did today | Trust: what the hooks do, without opening settings.json | `.cockpit.json paths` hook_settings (settings.json files), hook_logs |
| The context the autopilot cut today (one line) and Log (N): the autopilot's actions today and the balancer's choices of 24 h, merged by time, newest first; a row from another day shows its date | Trust: everything the cockpit and the balancer did by themselves | actions.jsonl, balancer log |

## Controls (phase 2), each proves its effect

| Control | Allowed when | Effect check shown on screen |
|---|---|---|
| Compact <session> | idle, above its sweet spot, notes saved during its last turn (see "Notes saved") | the next `compact_boundary` record: before and after tokens |
| Clear <session> at task end | idle, its bead closed (or a role with no bead), notes saved during its last turn (see "Notes saved") | its next turn's context size |
| Effort low/medium/high/xhigh | session running; keeps the cache | the pane's status line shows the new effort |
| Start with the recommended window from next launch | always | written to team.json; applied at next launch with `--autocompact <n>`; never `/autocompact` (it saves per model for every session), except the autopilot's window step below |
| Model change | only together with a clear or at launch (a model switch rewrites the whole cache) | the next turn's model in the transcript |
| Pause / resume the team | always | a hook blocks commit, push and bead claims; the cockpit shows no commit and no claim since the pause |

How commands reach a session: herdr types into the session's own pane, as the panel does today
(`herdr agent prompt <pane> <text>`).

## Autopilot rules (on by themselves from phase 3, the owner 2026-10-16; every action logged with before and after)

At most one control per session per read, in this order, never to a session whose last control waits for its proof:

A compaction the autopilot types into a Haiku session asks for a summary under 400 words (`compact_text.py`; panels f68cd6 to
b31e2b): the coordinator re-reads about 54k after each one against Claude Code's ~98k window, and its summary was 8k of it.

0. Compact over the ceiling (pg-45v5 ruling, owner grill q1 E): a session whose context is over its ceiling is compacted
   as soon as its turn ends, busy all day or not. Ceiling: P + q*C'/r (COMPACTION.md cost model: carrying a chat of
   1/q turns costs one compaction), within 1.25x to 2.5x its sweet spot; shown in its detail.
   Turn line (panels f68cd6 to b31e2b, 2026-10-22): below the ceiling, an Opus or Sonnet session over its sweet spot, at
   most `turn_end_max_tokens` (150k), is compacted once its turn has ended: idle `turn_end_gap_seconds` (20 s), and at
   most `turn_end_window_minutes` (10) after it, else rule 2 decides. Unsaved notes do not hold it; the thrash guard and a
   base over the line do. Haiku has no turn line. Why: the replay of 7 days of transcripts put the cost bottom at 150k for
   9 of 12 sessions, flat to 200k and rising fast past 225k, while the ceilings cut them at 210k to 274k: -$39.68 a day.
1. Keep Haiku sessions under 100k: removed 2026-10-22 (panels f68cd6 to b31e2b). Claude Code's own window, which the
   autopilot sets just under the 100k step, compacts a Haiku session there by itself; the guard on top refilled within
   minutes, a compaction every 3 minutes, and saved nothing (the replay of 7 days: $14.81 a week without it, $16.86 with it).
2. Compact idle sessions over their sweet spot, with no TASK coming (design pg-o1sq Q8 rows 5 to 7): just before its
   cache expires (`cache_expiry_margin_minutes` before, at most half a 5-minute cache, and earlier again by the gap
   between the cockpit's last two reads, so a slow read cannot skip the window: brain, pg-o1sq relaunch HOLD finding 2),
   unsaved notes do not hold it, since its summary keeps the unsaved work and waiting is how it misses the window
   (brain, pg-o1sq finding 3 answer). Past expiry it waits: the compaction would pay full price, so its next TASK decides. A session
   whose cache life is not known waits `autopilot_idle_minutes` as before.
3. A TASK arrives (design pg-o1sq Q6 and Q8 rows 1 to 4; never at a task end): decided once per TASK, just before the
   courier types it, and logged as a `task_start` record with its case. Warm cache: under its sweet spot, keep; over
   it, clear when Jev says the bead starts fresh and nothing below keeps it (brain, step 3 review: a summary of
   unrelated work is worth less than a clear), else compact. Cold cache and over its line, never kept (brain, pg-o1sq relaunch HOLD finding 3): compact when the bead needs its
   history, when it is related, when Jev has no verdict on that bead, for a session that holds a bead in progress or is
   a role session, or when the bead names no folder or shares one with the finished bead (the owner, 4f79d1); clear
   otherwise. Cold and under its line: keep in those same cases; clear otherwise. Unsaved notes block a clear only (brain, pg-o1sq finding 3 answer): a compaction's summary keeps
   the unsaved work, so a compact still runs; a clear over its line becomes a compact, under its line it is kept. Each clear logs a `cleared` record with its last task's files; when the next session reads one
   of them in its first 3 turns, a `wrong_clear` record. A session with 2 wrong clears in 7 days is only kept. The
   courier holds the TASK until the compact or clear is proved. The owner's own chat with brain is not a TASK, so
   nothing happens (row 8).
4. Jev's model, only when the cache is cold or the session is fresh (the owner: "que pasa cuando la cache es
   invalidada? revisa el balanceo de cswap"): idle past its cache's life (1 h, or 5 min for a 5-minute cache), as the
   balancer moves only cold sessions. `/model <id>`; proof: its next turn's model.
5. Jev's effort (keeps the cache): `/effort <level>` when it differs.
6. Launch flags (the owner 2ae134, pg-gg6c): a session that runs without one of its full flags (team.json's `launch`
   list, or `--dangerously-skip-permissions`, plus `--name agent-<role>`) is relaunched once per session id and
   command, idle past its cache's life. Its live flags are the argv of its process from `herdr pane process-info`
   (brain, pg-o1sq relaunch HOLD 5f13ab8); without that argv only the `--settings` and `--plugin-dir` `ps` shows are
   checked. The relaunch keeps its live `--model` and `--effort`: `/exit`,
   then, once its process is gone, `Q_TERM=1 claude --resume <id> <flags>` typed into its pane's shell (`herdr pane
   run`). A launch with flags gets none of its saved ones, so team.json lists them all. Proof: a process started after
   the `/exit` (its live record's `startedAt`) whose herdr argv carries every flag the resume typed; one without them
   fails it. A start mode line is no proof: a resume can write none (brain, pg-o1sq relaunch HOLD). A session still running 5 min
   after its `/exit` is dropped and logged.
   Jev's plugin picks, the plugin catalog and the cockpit's own launch settings files are removed (the owner, panel
   7671bc: the autopilot no longer handles effort, model or plugins).

7. Keep-warm probe (mb-s347.1 step 2; owner decisions e19cd7, 522555, da7c4a, 89423b of 2026-10-22; off until `keep_warm_probe_on`
   is true): an idle session in the window of rule 2 (`cache_expiry_margin_minutes` before its cache expires) gets one
   short fixed prompt, so its cache is read instead of rewritten. Only at or under `probe_max_spot_multiple` (1.75) times
   its sweet spot, and never over its ceiling or as a guarded Haiku, nor after a compaction newer than its last request
   (nothing of the new context is cached yet; panels f68cd6 to b31e2b: 4 of 6 cold probes of 10-21 and 10-22 came after one). At most the break-even count per idle stretch: the
   probes that cost what the cheaper of a cold rewrite and an idle compaction costs at its context, from its price card
   (about 38 on the Opus and Sonnet 5.5 cards). The count resets when the session turns busy or takes a turn of its own;
   the probe's own turn does not reset it. Jev decides, asked once per hour of a stretch (`wake` judgments): wake within
   the hour, probe; hours later, probe under its sweet spot and compact while warm over it (rule 2); never, nothing at all.
   Without a Jev forecast nothing is probed. The prompt goes through the same pane path as every control, which types only
   into an empty input box, so a session on a dialog gets nothing. Proof: the probe turn's request read about its whole
   context from the cache; a rewrite refutes it. Each probe is an `actions.jsonl` `sent` line (kind `probe`) and a
   `probe_sent` line with its count and cap. Why: the replay of 7 days (`tools/idle_replay.py`) priced $25.85 a day for
   rewrites today against $6.30 with this policy; the Max-plan quota weighting of cache reads is not known, and the policy
   moves 5.7 times the raw tokens.

Rules 4 and 5 are off (`jev_model_rule_on`, `jev_effort_rule_on` false in `config/thresholds.json`, brain's J5): Claude Code
saves a typed `/model` or `/effort` in `~/.claude/settings.json` as the default of every new session on every account,
which CLAUDE.md "Never" forbids. Each rule's row under Background jobs says so. Models are to switch by relaunch with
`--model` instead (owner ask 784930). A session whose transcript is not read yet (no turn known, as on the first read
after a start) gets nothing from any rule (brain's J7).

Nothing is typed, and Jev is not asked, while the team is paused (the owner, 2026-10-16: only the jobs that touch
sessions or cost stop; the read and the price check go on). A /model or /effort is not typed again until the session's next turn proves
or refutes it; a pane herdr refuses is left alone for 30 minutes and logged once. Rules 4 and 5 change nothing a compaction could drop, so they do not wait for saved notes (brain's J2). Every skip of rules 1, 2, 4, 5 and 7 is written to actions.jsonl when its reason starts, so the thresholds are calibrated from
what the rules did and did not do (`docs/CALIBRATION.md`).

Message interception (courier, outbox, inbox, send gate, herdr guard, one task in flight) was removed 2026-10-19
(the owner: "elimina todo lo que tenga que ver con interceptar mensajes, deja el cockpit solo para suggestions, solo compact o clear").
Sessions message each other directly. Rules 4 and 5 (Jev's model and effort) were removed the same day.

### Jev's two verdicts (owner 96051b, pg-o1sq step 2: design Q1, Q4, Q12)

| Element | Purpose | Source |
|---|---|---|
| Session verdict: one Jev request per running session with four yes/no questions about its work as a whole (deep reasoning, mechanical, wide reading, a costly mistake). Jev sees its role line from team.json, whether it coordinates, its open beads (held first, at most 8, descriptions cut to 600 characters), its last task and the files it touched, its last 6 turn lines (cut to 500 characters each, never the whole transcript), the milestone with its goal and definition of done, its context against its sweet spot and idle time, and its account's 5 h and 7 d use. Asked again only when its role, its beads or the milestone change. A fixed table turns it into model, effort and window: deep reasoning or a costly mistake is Opus (xhigh from 0.85), else mechanical is Haiku, else Sonnet; a design, architecture or security label on any of its beads floors deep reasoning at 0.9. The owner's "wrong" clicks join with step 5 | The model fits the session's role and all its work, not one bead: Jev's bead answer once put brain on Haiku (jev_record, pg-z061) | Jev, team.json, bd, dod.json, goal.json, transcripts, cswap |
| Team health "Cache rewrites": per session, each request of 24 h that wrote over half its context to the cache, by cause: clear (a session's first request), compact (first after a compact_boundary), expiry (after the cache's life), settings change (model or effort differs from the request before), unknown (an account move, a relaunch, an evicted cache); tokens written per cause and totals; WATCH when a settings change or an unknown cause rewrote one (pg-45v5) | Which setting rules cost a full rewrite, so model, effort and plugin changes ride on a rewrite that happens anyway (owner, grill 20261018-172831 q2) | transcripts (~ heuristic: the half-context share) |
| Team health "Jev's own cost": Jev's requests, questions and the input and output tokens TypeSafe returns in `usage`, for 24 h and 7 days, one line per request in `~/.agent-cockpit/jev_calls.jsonl` (cache hits make no request); WATCH when its 24 h tokens pass 1% of the team's tokens without cache (pg-45v5) | Whether the judge costs less than the decisions it makes save (owner, grill 20261018-172831) | TypeSafe response `usage`, transcripts |
| Team health "Rework": each bead closed in 14 days with its HOLDs before its first GO, whether it was reopened (a `bead_reopened` record when the cockpit saw it closed and then open), and the fix beads created within 7 days after its close that name it; verdict correct (GO with no HOLD before it, no reopen, no fix bead, a fix being a bug or a bead that says fix) only once its 7 days have passed, else pending; rework at once; a bead with no GO-REQ or no GO is not reviewed and not judged; before 2026-10-14 a GO or HOLD finds its bead by its sha256, through the GO-REQ whose patch file is pg-<bead>-vN.patch (pg-45v5, owner q6, brain's ruling) | Whether tokens saved cost quality: the acceptance week's "correct task" | the board (bd), GO-REQ, HOLD and GO messages (14 d), actions.jsonl |
| Team health "Per task, compared": tokens without cache per finished task (median and mean) by role, bead type, model and effort, for beads closed in 14 days, each group with its size and "small" under 5 tasks; a request counts for the bead its session started last and had not closed (~) (pg-45v5) | Which role, bead type, model or effort costs more per finished task, read with its sample size before any setting changes (owner q6) | the board (bd), transcripts |
| Bead verdict: only between tasks, one request for its next bead (needs history, related to its last task, long). It carries its context when the bead needs history or is related; the task-end rule (rule 3) compacts then, and the length waits for the Q8 table (step 3) | Compact or clear is decided about the next bead, which is what it is about | Jev, bd, transcripts |

### The owner's wrong click (owner 96051b, pg-o1sq step 5: design Q5, Q4 G)

| Element | Purpose | Source |
|---|---|---|
| "Wrong" on each autopilot decision in the Background jobs log (every control it sent, and every TASK it kept, shown as a kept row) in the last 7 days. The click writes a `wrong` record. A relaunch that carried Jev's plugins is undone at the session's next idle moment, never mid-turn: `/exit`, then the same session id resumed with team.json's own flags (`undo_sent`). A compact or clear only stores the label (its context is gone), and so does a keep, a team.json relaunch, and a model or effort step (a typed `/model` or `/effort` is saved in ~/.claude/settings.json). The row then says what the click did | The owner corrects a decision instead of approving each one (Q3 B rests on it) | actions.jsonl |
| Jev's session and bead verdicts see the session's latest 5 wrong clicks (the decision and its kind), and a new click asks Jev again | Jev learns from the owner's corrections (Q4 G, Q14) | actions.jsonl `wrong` |

### Outcomes and good use (owner 96051b, pg-o1sq step 6: design Q11, Q13)

| Element | Purpose | Source |
|---|---|---|
| Team health "Autopilot outcomes": per session, tokens per finished task without cache and re-reads (24 h), clears that lost work, HOLDs it got, the owner's wrong clicks and its TASK starts by action (7 d). WATCH on any wrong click or clear that lost work | Whether the autopilot's decisions pay, the outcomes the re-fit (step 7) learns from (Q11 A to D; red gates stay under Main) | transcripts, actions.jsonl, HOLD messages |
| Team health "Good use": per session, the share of cache traffic served from cache, cache writes never read before the cache's life ran out (heuristic), over its sweet spot, Claude Code's own compactions (24 h), and whether its first turns after its last SessionStart (start, resume, clear or compaction) read its state file again ("no state file" only when no project_<role>_state.md exists for it; MEMORY.md holds only a pointer to it). Jev's session verdict reads the last one. WATCH when a session reached Claude Code's own compaction line. Names where the team-wide measures already are and which are not measured yet | Whether each session's config uses the cache and its context well (Q13; the owner: "buen uso de la cache ... de la memoria ... de los recursos") | transcripts |
| Team health "Hook output": per hook script, the size of its last output in the running sessions' transcripts (the whole stdout, not the stub), which session ran it and when; ACT at 10,000 characters or more (calibration step 5) | Claude Code keeps only 10,000 characters of a hook's output for the model and puts a 2k stub with a file path in its place, so a start hook over it fails silently | transcripts: hook_success stdout (measured) |

### Quota per finished task (pg-o1sq, owed before close: design Q13)

| Element | Purpose | Source |
|---|---|---|
| Team health "Quota per task": per account, its 7 d use now, the 7 d points it spent in 24 h (the sum of its rises in the metrics history; a weekly reset is not spending) and the tasks its sessions closed in 24 h, with points per task; the team's figure as its value. Heuristic: a session counts on the account it runs on now. Jev's session verdict reads its account's points per finished task with its quota | Whether a config spends the team's quota well for the work it finishes (Q13), and Jev sees it | cswap through metrics.jsonl, transcripts |

### Docs against code (pg-o1sq, owed before close: design Q13, Team health only)

| Element | Purpose | Source |
|---|---|---|
| Team health "Docs against code": each tracked doc (docs/, README.md, CLAUDE.md of every team repo, but the logs in `docs_not_describing_code`) that names a file whose last commit came more than `doc_lag_days` after the doc's own; 90 days of git log, read once an hour. Only a path in the same repo's log counts | Where a session would read a doc that no longer matches the code (Q13: "docs older than the code they describe") | git log, the docs on disk |

### Learned numbers (owner 96051b, pg-o1sq step 7: design Q14)

| Element | Purpose | Source |
|---|---|---|
| Once a day each number with a `range` in config/thresholds.json (status `learned`: min, max, max_weekly_change_pct) is fitted again from the logs when its fitter has 10 samples. A fit inside its range moves it, at most its weekly change from where the week started, logged in `~/.agent-cockpit/learned.jsonl` and applied again after a restart; config/thresholds.json is never rewritten. Fitted now: `cache_expiry_margin_minutes` (95th percentile of the autopilot's compactions' time from send to their compact_boundary, plus one read). And `jev_yes_probability`: every `task_start` keeps Jev's bead and session scores, the cut-off it was read at and its control id; a start that did what Jev said is labelled wrong by a wrong click or a wrong clear, right after a day without one; from 20 labels the cut-off that gets most right. And `recovery_idle_gap_minutes`, the sweet spot's recovery input: the 99th percentile of the team's gaps inside a turn (no prompt between two requests), from 100 gaps, read by the transcripts on every read. A number stays `provisional` until its first change. Team health "Learned numbers": each number, its range and its last change | The code's numbers follow what the team does without a commit per tweak, and never far or fast (Q14) | config/thresholds.json, learned.jsonl, actions.jsonl |
| Learned numbers also says how many TASK starts of the last two weeks Jev's cut-off measured and how many it left out as confounded: its model, effort, plugins or task changed, its process started again or Claude Code auto-compacted it before its outcome (pg-6inz) | Whether a cut-off change comes from Jev's verdicts or from something else that changed at the same time (owner b289d0 C) | actions.jsonl `task_start`, `sent`, `task_delivered`, `process_started`, `auto_compacted` |
| A fit outside its range changes nothing and is a Your tasks row with the value and the fit | The owner decides a move the range does not allow (Q14) | learned.jsonl `proposal` |

### Notes saved (fix of 2026-10-16: the check compared against the end of the last turn)

A session saves its notes during a turn and replies after, so a bead update is almost always older than the end of
that turn. The check therefore compares against the start of the last turn: the last prompt that was not a tool result
(a slash command such as `/effort` starts no turn and does not count). One value, `notes_saved`, feeds the Memory
light, Compact, Clear and every autopilot rule.

| Element | Purpose | Source |
|---|---|---|
| `notes_saved` for a session with a bead: one of its beads changed at or after the start of its last turn | A compaction or clear drops what the session worked out; a bead update during the turn shows it wrote that down first. Against the end of the turn it was False for sessions that had saved, so they were never compacted | bd (bead update times), transcripts (the last prompt that was not a tool result) |
| `notes_saved` for a role session (brain, coordinator, reviewer, reviewer-2), which holds no bead: its state file `memory/project_<role>_state.md` changed at or after the start of its last turn. A missing file counts as not saved | These sessions had no check at all (no bead, so they passed). Their memory is their state file | the project's `memory/` folder under the transcripts folder, read only (`~/.claude` is never written) |
| Autopilot skip reason for a role session: "its state file project_<role>_state.md has not changed since its last turn started", in the log and in actions.jsonl | The owner sees why a role session over its sweet spot is not compacted or cleared | the same value |
| Brain is not cleared while an answer in panel.json is missing from the decision log (the "not in the decision log" list of Said vs saved); a compaction does not wait for it (panels f68cd6 to b31e2b, 2026-10-22: panel.json keeps the owner's exact words, and the hold let brain grow to 400k) | Brain writes DECISIONS.md; a clear would forget that it still owes those answers | panel.json, DECISIONS.md (Said vs saved) |
| Memory light judges an idle session only | A busy session is mid-turn and may still save; flagging it would light the Memory light on every turn | session state from herdr |
| `autopilot_on` is `true` and the pause file is its switch: Pause stops it, Resume starts it, window step first (the owner, 2026-10-16: "el autopilot automaticamente se pone true cuando le de a resume") | One switch for the team and its autopilot; nothing is typed while the team is paused | `~/.agent-beads/paused`, `config/thresholds.json` |

The autopilot's window step (the owner, 2026-10-16; the one exception to "never change ~/.claude"):

| Element | Purpose | Allowed when | Effect check |
|---|---|---|---|
| Autopilot on: `/autocompact 1000000`; off: `/autocompact 200000`, typed once per model (Opus, Sonnet, Fable) per cswap account (each account has its own settings folder) into one live session of that pair, idle first; a pair whose session shows up later gets it then | With the autopilot on, the sweet-spot rules decide when a session compacts, not Claude Code's 200k window; off puts the 200k window back | the switch changes; never Haiku (the coordinator keeps about 130k); never while `~/.agent-beads/paused` exists (logged once as held, nothing typed; sent once the file is gone, since the switch still differs from what was last set) | each one logged in `actions.jsonl`; proved (done) when the account's settings file, read only on every read after typing, holds `modelSettings.<model>.autoCompactWindow` at the typed value; checked again (confirmed, or failed) by that session's next decisive `compact_boundary.preTokens`: on is confirmed by a compaction above 200,000 and failed by an auto compaction at or under it; off is confirmed by an auto compaction at or under 200,000 and failed by any compaction above it; a manual compaction at or under 200,000 proves neither |
| Haiku: `/autocompact <its sweet spot window>` (trigger plus 33k, 100k to 1M; a trigger at the 100k step is held 5k under it), retyped whenever it changes; none before it has a sweet spot (the owner, 2026-10-17: the autopilot "debe decidir absolutamente toda la config sobre la marcha de una session") | Claude Code itself compacts the coordinator before the 100k step when the autopilot cannot act; the old fixed 200k let it sit at 155k paying 5 times | always, never while paused | the session's next automatic compaction near the window minus 33k |
| Proof of any window step: a compaction only, never the settings file alone (brain's report F11: a project file's 300k beat the saved 1M) | "Done" means the window really applies | | automatic compaction within 20k of the window minus 33k proves it; one well below refutes it |


## Cut from the first mockup, and why

| Cut | Why |
|---|---|
| Nine equal big-number tiles | Hero-metric slop; normal items should be quiet |
| Messages column per session | No decision hangs on it |
| Coordination section (median messages, review-round distribution) | Historical; kept as one process line and as actionable rows |
| "History costs more than new work above …" | Repeated the sweet spot; the number was not computed |
| Jev model suggestion rule | Moved to phase 3 with Jev, the owner's choice |
| Mode buttons normal/intense/away/off | Nothing read them; replaced by an enforced pause |
| Milestone percent bar | Inflated: 85% while the goal stood at 2 of 10 |
| "Is the team on Mn?" (seven checks, "Show the N that pass") | The owner, 2026-10-16: four were shown elsewhere (work off the milestone is a Needs you row; a criterion nobody moves is amber on its tile; a stuck bead has its mark; main green is the Main light); the other three became the "Team rules broken" row |
| Blocker ask as a Needs you row | Shown twice; it stays in Your asks only (the owner, 2026-10-16) |

## Decided 2026-10-16, not built yet (the owner, in the build chat)

| Element | Purpose | Source |
|---|---|---|
| Tokens, its own section: tokens per day (7 d), each session's 24 h, who spends most, the share spent above each session's sweet spot. Sessions keeps state, context and work | Built 2026-10-16 (Tokens, above) | transcripts, deduped |
| Background jobs, its own section, replacing the Autopilot block | Built 2026-10-16 (Background jobs, above) | actions.jsonl, balancer log, collector |
| Price check, daily: read Anthropic's prices page once a day and say in the header when it differs from `config/prices.json`; the 90-day mark stays | Built 2026-10-16: the markdown page's first table; a failed read is tried again in an hour | Anthropic prices page, prices.json |

## Phase 3 build notes (2026-10-16; the owner: "arranca con la fase 3, más adelante te paso Jev")

| Element | Built | Purpose |
|---|---|---|
| Autopilot, two rules, always on | After every read it types `/compact` into a session the rules pick, through the same path as the owner's controls; never into a session whose last control still waits for its proof. `autopilot_on` in `config/thresholds.json` stops it (no switch on the page) | Context kept near each sweet spot without the owner (the owner: "debe ser autobalanceado") |
| Autopilot log (`~/.agent-cockpit/actions.jsonl`) and "What it did today" | Every control, the owner's and the autopilot's: before, reason, and its proved outcome. Today's rows, and the context its proved compactions cut | Trust: every action the cockpit took on its own, with its measured effect; phase 3 is done after a week of it |
| Tokens per day, 7 days (Tokens since 2026-10-16) | From transcripts, today so far last | Whether compaction brings the team's spend down |
| Jev suggestion per session (shadow mode) | Replaced by Jev's two verdicts (pg-o1sq step 2) for the session's settings; the bead questions below still give an unlabeled bead its task kind. Connected 2026-10-16; since the design chat's J1 (the owner, 2026-10-16: close every gap): the bead's own fields first (a milestone or epic gets none; `chore` or a `mechanical` label is mechanical without asking Jev; `design`, `architecture`, `security` labels floor deep reasoning at 0.9), then four yes/no Choice questions to Jev in one request per bead text (mechanical, deep reasoning, needs history, wide reading), then a fixed table: model and effort, weight (light, medium, heavy; J5), start (carry its context or fresh after a clear) and window (small or large). A probability of `jev_yes_probability` (0.6, provisional) counts as yes. Key from `JEV_ENV`; shown, never applied | Which model and effort each task needs, beside what the session runs; applied only after the Jev record says the table saves tokens without more HOLDs |
| Jev record (`~/.agent-cockpit/jev_record.jsonl`) | Built 2026-10-16 (the owner: "Build the Jev record"): a `suggested` row when a suggestion or what runs changes (bead, Jev's model and effort, the model and effort that ran), an `outcome` row when the bead closes (its holder's tokens and turns between start and close, HOLD messages on it, `partial` when it ran longer than the 14 days of transcripts read). Per class under Background jobs, with the day it can be judged (14 days after the first row) | Without it, shadow mode decides nothing: after two weeks, whether a class saves tokens without more HOLDs |
| Milestone share of tokens per session per day | Not built | Transcripts do not say which bead a turn served; deferred until a need asks |

## Phase 2 build notes (2026-10-16; the owner: "continúa con la siguiente fase")

| Control | Built | Proof shown |
|---|---|---|
| Compact <session> (session panel; Needs you "Compact" on a Haiku row) | Typed into its pane with `herdr agent prompt` when allowed | its next `compact_boundary` record: before and after |
| Clear at task end | Typed `/clear` when idle, no bead in progress, notes not unsaved | a new session id on that session, with its context |
| Effort low/medium/high/xhigh | Typed `/effort <level>` | its next turn's effort in the transcript |
| Apply the recommended window | Not built: launches do not read team.json yet (team dependency 8) | |
| Pause / resume the team | Not built: needs the pause hook (team dependency 7, brain) | |

Each control is refused with its reason when its rule does not allow it, and shows "waiting" until the transcript
proves it, or "not seen" after 15 minutes. Sent controls are kept in memory while the cockpit runs and logged to its
terminal. Other Needs you actions still copy a prompt.

## Phase 1 build notes (2026-10-16)

| Element | In phase 1 | Why |
|---|---|---|
| Header: unavailable sources | "N sources unavailable" (amber) for a broken source; "N sources not set up yet" (quiet) for one that waits on a team change (balancer log, team.json, gate logs) | Trust: a missing number is named, never shown as zero; an expected gap is not a warning (the owner, 2026-10-16) |
| Header: Pause the team | Not shown | No effect until the pause hook exists (phase 2, dependency 7) |
| Needs you actions | Copy the command or prompt; "Answer" and "See sessions" open their section | Phase 1 writes nothing but an answer; the owner pastes it into the pane |
| Owner's criterion without an ask | "Ask brain to add it" copies a prompt for brain | The cockpit cannot invent an ask's options or recommendation; brain adds it with `ask_owner.py add` |
| Missing id | Bead ids only | Ask ids (6 hex) cannot be told apart from commit shas in a reply |
| Handled by itself | Only what the balancer handles | The autopilot is off until phase 3, so nothing else is handled |
| Session panel | Compact copies `/compact` when allowed; recommended window as text; effort shown, not switchable; no clear button | Controls arrive in phase 2 with their effect checks |
| Grill thread comments | Answered in the thread as "not forwarded" | Sending to a session is phase 2 |
| Autopilot | Rules listed, marked as running by themselves from phase 3; no switches | The owner, 2026-10-16: it balances itself, the owner does not configure it |
| Silent bead | Not a Needs you row. A "stuck" mark in the sessions table and on its criterion's tile | The owner, 2026-10-16: "no quiero warning o notificaciones, solo una marca". A bead counts as stuck after 12 h with no bead update and no turn by its holder |
| Blocker ask waiting | Shown at once, not after 1 h (in Your asks and on the Asks light since 2026-10-16, no longer in Needs you) | The owner, 2026-10-16: "yes of course"; the session that asked waits for the answer (panel 4c9041) |

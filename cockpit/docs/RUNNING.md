# Running the cockpit on the Mac

Phase 1: read only, except answering an ask through `ask_owner.py answer`. Python 3.9 or newer, standard
library only, nothing to install.

## Start

```
cd ~/Documents/agent-suite
git fetch origin && git checkout main && git pull
python3 -m unittest discover -s tests -t .      # expect: Ran 374 tests ... OK
python3 cockpit.py                              # prints http://127.0.0.1:8765/
```

Open the printed url. The page fits one screen: Team health, ten areas on top (a click opens its detail band under them), then
two columns that scroll by themselves (the milestone, Needs you, your asks, said vs saved; sessions, tokens, accounts,
background jobs). Click a section's header to close or open it, and any row
to see its full text and source. A light opens its section. Below 1100 px wide it is one column. Ctrl-C stops it (and the grill server it started). `python3 cockpit.py --demo` runs the
same page on `fixtures/` with the clock at the Oct 15 snapshot, if you want to see it without your data.

No restart after a pull: the cockpit re-executes itself, same arguments and environment, within 2 s of a `.py`,
`config/` or `.cockpit.json` file changing, and writes its pid to `~/.cockpit/cockpit.pid`. Code that does not
import, or a config that does not load, is logged and the old code keeps running. The page reloads itself when the server restarted or a `page/` file changed, unless
something is staged to send.

## Before the first run: .cockpit.json

The project's settings are one file, `.cockpit.json` (keys `port`, `paths`, `team`), merged over the global
`~/.config/cockpit/config.json` if it exists; the project's value wins. Both are checked at start: an unknown key, a
wrong type or a missing key stops the cockpit with one line naming the file and the key. Without `--project DIR` the
cockpit runs on its own folder's `.cockpit.json`, the project's. `config/thresholds.json` and `config/prices.json` stay
shared by every project.

A project with no beads, no panel of asks or no milestone leaves those keys out: no `paths.board_dir` and
`paths.bd_command`, no `paths.panel` and `paths.ask_owner`, or no `paths.milestone_dir` (where `dod.json` and
`goal.json` live). The cockpit starts, leaves those sections off the page and does not count them as broken sources.

Every path is the default from `docs/DATA_SOURCES.md`. Check these four on your Mac:

| Key | Default | Check |
|---|---|---|
| `node` | `~/.nvm/versions/node/v22.23.2/bin/node` | grill-with-ui needs Node 20+; your default node is 18 |
| `grill_server` | `~/Documents/project/.claude/skills/grill-with-ui/server.mjs` | the pinned skill in the project repo |
| `bd_command` | `bd export --all` | must print one bead per line on stdout; if not, tell me what `bd export --help` says |

`team_json` points at `~/.agent-board/team.json`; until it exists the drift column stays blank and the header
says so.

## The header tells you what it could not read

"N sources unavailable" next to "the project" opens the list of every source that failed, with its error. A failed source is never shown as
zero. Expected today: the balancer log (pg-81e3) and team.json (dependency 8).

## What to check, three numbers per section (phase 1 is done when these match)

Run each command in another terminal and compare with the page.

### Needs you
1. Silent beads: the rows that say "has had no update for N h".
   `cd ~/.agent-board && bd list --status in_progress --json | python3 -c "import json,sys,time,datetime as d; [print(b['id'], b.get('assignee'), round((time.time()-d.datetime.fromisoformat(b['updated_at'].replace('Z','+00:00')).timestamp())/3600,1),'h') for b in json.load(sys.stdin)]"`
   Every bead over 6 h has a row (comments can make a bead younger than its updated_at).
2. Work off the milestone: for each bead named, `bd show <id> --json` shows a parent under another milestone and priority above 0.
3. Team rules broken: the row names every task session holding more than one bead in progress
   (`bd list --status in_progress --json | python3 -c "import json,sys,collections; print(collections.Counter(b.get('assignee') for b in json.load(sys.stdin)))"`).
   A blocker ask is not a row here: it is in Your asks, and the Asks light says ACT.

### Milestone
1. Goal: `cat ~/.agent-board/goal.json`; the page's "Now X of Y, target Z" is the same three numbers.
2. Done criteria closed: `python3 -c "import json,subprocess; ids=json.load(open('$HOME/.agent-board/dod.json'))['milestones']['pg-a18q']['dod']; print(sum(json.loads(subprocess.run(['bd','show',i,'--json'],capture_output=True,text=True,cwd='$HOME/.agent-board').stdout or '[{}]')[0].get('status')=='closed' for i in ids), 'of', len(ids))"`
3. Log (N) at the bottom: the beads under the milestone closed in the last 7 days; N is the same as "closed in 7 days"
   under the bars.

### Sessions
1. Context: in one session's pane, its status line (or `/context`) shows the same context as the bar's first number, within one turn.
2. Account: `ls ~/.claude-swap-backup/sessions/*/sessions/` lists the pid of that session under the account the row shows.
3. Sweet spot inputs: `python3 research/scripts/calibrate_sessions.py --days 2` prints g and P for the same session; the panel's "How the sweet spot is worked out" shows the same g, and P matches its last compactions.

### Your asks
1. The count "N asks on the panel" equals the asks in `panel.json` (command in Needs you, check 3).
2. Answer one ask in the grill round below the list. Within a few seconds the list loses it, Log (N) at the bottom
   of Your asks grows by one and lists it with your words, and `python3 ~/.agent-board/ask_owner.py list` no longer lists it.
3. The answer in `panel.json` `answered[]` is the option's own text, or exactly what you typed.

### Accounts
1. to 3. `env -u CLAUDE_CONFIG_DIR cswap list` shows the same 5h and 7d percent and reset times for three accounts.

## Phase 2: controls

Open a session's row in Sessions: **Compact**, **Clear at task end** and **Effort** type into that session's herdr pane
(`herdr agent prompt`). A disabled button says why. After a click the row shows "waiting" until the transcript proves
it (a `compact_boundary` record, a new session after `/clear`, the next turn at the new effort), or "not seen" after
15 minutes. Log (N) at the bottom of Sessions lists today's controls with their results, after a restart too. Check one by looking at the session's pane. `/effort` is typed as `/effort <level>`; if your Claude Code
does not take that command, the control stays "not seen": tell me.

Drag a section by its grip (the six dots), or focus the grip and use the arrow keys. The order is kept in this browser.

## Phase 3: the autopilot runs by itself

As soon as the cockpit runs on your data, the autopilot types `/compact` into a session when one of its two rules
holds: idle 10 minutes or more over its sweet spot with its notes saved (or no bead in progress), or a Haiku session
idle at 90k. It never sends again to a session whose last compaction has not shown yet. Log (N) at the bottom of
Accounts lists what it did today with each result, beside the balancer's choices of the last 24 h, and every action is in `~/.cockpit/actions.jsonl`. Pause stops it and Resume
starts it, window step first. To stop it for good, set `autopilot_on` to `false` in `config/thresholds.json` and restart
the cockpit.

### Jev (shadow mode)

The cockpit reads Jev's key from the environment variable `TYPESAFE_API_KEY`, the same key the project repo keeps in
its `.env.local` (the owner, 2026-10-17: one name for the TypeSafe key). The endpoint and the model, `jev-latest`, are
fixed in `cockpit/classifier/jev_classifier.py`. Load only that line in the shell you start the cockpit from, without
printing it. fish:

```
set -gx TYPESAFE_API_KEY (string replace -r '^TYPESAFE_API_KEY=' '' -- (grep '^TYPESAFE_API_KEY=' ~/Documents/project/.env.local))
```

zsh: `export TYPESAFE_API_KEY="$(sed -n 's/^TYPESAFE_API_KEY=//p' ~/Documents/project/.env.local)"`.
Check with `[ -n "$TYPESAFE_API_KEY" ] && echo set`, and start `python3 cockpit.py`. Each running
session's panel then shows "Jev suggests <model>, <effort> for <bead>: confidence ...". It is shown only, never
applied. Without the key it says Jev is not connected, under "sources not set up yet".

## Background jobs, tokens, prices and the Jev record

- **Background jobs** lists what runs by itself: the autopilot's two rules, the balancer, the 30 s read, the daily price
  check and the Jev record, each with when it last acted and what it did. Open a row for its rule and the sessions it
  left alone. Log (N) at its bottom merges the autopilot's and the balancer's rows by time.
- **Price check**: once a day the cockpit reads `https://platform.claude.com/docs/en/about-claude/pricing.md`
  (`.cockpit.json` paths.prices_page; a plain GET, nothing is sent) and the header says "prices differ from Anthropic's
  page (N)" when `config/prices.json` does not match. Check: change one price in `config/prices.json`, restart, and the
  header names it.
- **Tokens**: compare a session's 24 h with `python3 research/scripts/calibrate_sessions.py --days 1`. Sessions are
  matched by their transcript title (`old-<role>`), so tokens from before a `/clear` count too.
- **Jev record**: `~/.cockpit/jev_record.jsonl`, one `suggested` row per bead (again only when the suggestion or
  what runs changes) and one `outcome` row when the bead closes. `tail -3 ~/.cockpit/jev_record.jsonl`.
- **Needs you** buttons that name a team session ("Tell the coordinator", "Tell brain") now type their
  prompt into that session's pane; the row dims with "Sent", then "Done" once its next turn starts.

## Your asks, pause, and the Jev rules (2026-10-16, session 4)

- **Your asks**: open a row to answer it: click an option, or type your own words and Save. It is saved at once with
  `ask_owner.py answer`; the row leaves the list and Log (N) grows. Tick asks and press "Open a grill round for N
  ticked" for a grill round in its own tab; a comment in its thread is typed into the pane of the session that asked.
- **Pause the team** (header), or `python3 tools/team_pause.py off|on|status` (the same switch brain uses): writes `~/.agent-board/paused`; brain's hook (TEAM_DEPENDENCIES 7) blocks commits,
  pushes and bead claims while it exists. The banner shows any commit or claim made after the pause.
- **The autopilot applies Jev** (Background jobs lists each rule): effort at once, model only when the session's cache
  is cold, and clear or compact at a task end. Each action is in `~/.cockpit/actions.jsonl` with its reason and
  proof; `grep '"origin": "autopilot"' ~/.cockpit/actions.jsonl | tail`.
- `/model <id>` is typed as `/model claude-sonnet-5-5`; if your Claude Code wants another form, the action stays "not
  seen": tell me.
- **The window step** runs when `autopilot_on` changes: `/autocompact 1000000` (on) or `200000` (off), once per model
  per cswap account. Check one account: `python3 -c "import json,glob; [print(p, json.load(open(p)).get('modelSettings')) for p in glob.glob('$HOME/.claude-swap-backup/sessions/*/settings.json')]"`
  shows `autoCompactWindow` at that value for each model typed into it; the session's Log row then says done.

## What is still not built

- Pause the team (needs brain's pause hook, team dependency 7) and applying a window (needs launches that read
  team.json, dependency 8).
- `cswap-relogin <slot>` is still copied for a terminal. "Answer" and "See sessions" open their section.
- The grill gaps (iframe header, thread comments forwarded, question age, the saved line): paused by the owner.
- A comment in a grill thread gets a reply saying it was not forwarded; ask the session in its pane for now.
- The milestone share of tokens per session (transcripts do not say which bead a turn served).

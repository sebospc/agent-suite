# Team protocol

How the sessions of one team talk: who sends what to whom, the message types, and how the lead and the coordinator
split the work. The guards in `tools/team/` enforce the parts a session slipped on more than once.

## Roles

| Role | Does | Never |
|---|---|---|
| lead | Sets order and priorities, writes each task, lands patches that have a GO, keeps the owner's decisions in the decision log with the owner's own words | Decides for the owner; writes in a worker's folder |
| coordinator | First point of contact for every session: keeps the board in order, every owner question on the panel, grants slots, hands the lead one ready package at a time | Answers for the lead or the owner |
| reviewer | Reviews a frozen patch and answers GO or HOLD, one line per finding; read-only | Writes anything |
| worker | Works one ticket at a time in its own folder; runs its checks before and after | Edits another session's folder; claims a second ticket |

Session names are the project's `session_prefix` plus the role (`agent-lead`, `agent-ios`). Each role's prompt
starts from `templates/roles/`.

## Rules for every message

- One event, one message, one recipient. Never send the same event to two sessions, never forward what the author
  already sent to its target.
- Progress goes on the ticket (`bd update ID --append-notes`), never in a message.
- No message that asks for no action: no "noted", "thanks", no repeat of a state that did not change.
- Line 1 is `<TYPE> <ticket> [vN]`, then one `key: value` per line, the required keys in the table's order, at most
  10 lines. Longer evidence goes in a file; the message gives its path.
- Paths, hashes (first 8 hex), commit shas and counts, never pasted content. Counts are `N passed, M failed,
  K skipped` with the log path.
- A relay quotes the author word for word (`send_guard.py` checks it).
- A message that misses a required key goes back as `BOUNCE`. The coordinator bounces; it does not fill the gap.
- Owner questions never travel as messages: they go on the panel (`ask_owner.py add`).

## Message types

| Type | From → to | Required keys |
|---|---|---|
| `TASK` | lead or coordinator → worker | goal, done-when, scope (folders), base |
| `GO-REQ` | author → its reviewer | patch, sha256, base, tree, changed, checks (each with log), guards, mutants, open, message |
| `GO` / `HOLD` | reviewer → author | sha256, base, tree, checks run (each with log), mutants run; `HOLD` adds one `path:line severity problem fix` per finding |
| `LAND-READY` | author → coordinator, forwarded unchanged to the lead | patch, sha256, base, tree, go (reviewer and time), message |
| `LANDED` / `PUSHED` | lead → coordinator | sha, tickets, verified (the line `verify_landing.py` printed); `PUSHED` adds the gate counts |
| `SLOT-REQ` / `SLOT-FREE` | worker → coordinator; coordinator → worker | slot (a name from the config's `slots`), minutes, run |
| `BLOCKED` | worker → coordinator | needs (who acts, what), since |
| `RULING-REQ` | coordinator → lead | question (one line), options, recommended |
| `RULING` | lead → coordinator | decision, why (one line) |
| `BOUNCE` | coordinator → sender | missing (key or rule) |

## The lead and the coordinator

1. Only the coordinator starts a message to the lead. Any other session writes to the lead only to answer it.
2. The lead writes each task as a ticket and queues it: `task_queue.py add SESSION TICKET`. The courier hands a free
   session its next ticket; the lead sends a `TASK` only when the ticket needs more than its own text.
3. A worker holds one ticket in flight (`task_queue.py`, `claim_block.py`). A ticket waiting on the owner moves to
   waiting (`task_queue.py wait TICKET --ask ID`) and frees the worker for the next one.
4. Slots: a worker sends `SLOT-REQ`; the coordinator runs `slots.py request SLOT SESSION` and answers with what it
   printed. On `SLOT-FREE` from the holder it runs `slots.py free` and tells the next holder.
5. GO'd patches go to the coordinator as `LAND-READY`; the coordinator hands the lead one package at a time.
6. The lead lands it, checks the landed commit with `verify_landing.py`, sends `LANDED`, then runs the board snapshot
   if the project uses one.
7. The team check (`team_check.py`) runs on a timer and wakes the coordinator only when it prints a finding.
8. A question nobody has put to the owner goes to the lead, who puts it on the panel. The lead never answers for the
   owner, and the coordinator never answers for the lead.

## Review by risk

The reviewer takes only the lenses that fit what the patch touched: `risk` (data, credentials, guards, a contract
others consume), `resilience` (errors, retries, partial writes, concurrency), `readability` (public APIs, messages,
docs), `reliability` (logic tests should pin). It trusts the author's receipt logs and runs only the targeted checks a
lens or a finding names. Only a severe finding the patch caused blocks. One fix round per frozen candidate; if the fix
still has a blocker, the lead decides: a new brief, a split, or one more round.

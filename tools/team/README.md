# Team tools

Hooks and scripts for a team of agent sessions. Each one reads its paths from environment variables (`AGENT_*`) with defaults under `~/.agent-board`, so a project points them at its own board.

| Tool | What it does |
|---|---|
| `ask_owner.py`, `panel_wait.py` | Every question to the owner goes on one panel with options, a recommendation and a why; the waiter reports answers |
| `send_guard.py`, `message_rules.py`, `transcript_tail.py` | One event, one recipient; a result line carries counts; a relay quotes the author word for word |
| `owner_ask_guard.py` | Blocks a reply that asks the owner something without a panel ask |
| `panel_write_guard.py` | Only the ask tool writes the panel |
| `claim_guard.py` | A reply that says something was saved or landed must name the sha, ticket or file |
| `receipt_guards.py` | A test receipt with skip markers or a lower count is refused |
| `pause_guard.py` | One file pauses every session |
| `engram_save_nudge.py` | Reminds a session to save to memory; after a compaction asks for a summary and a fresh role state |
| `verify_landing.py` | A landed commit must match the reviewed frozen patch |
| `nudger.py` | Nudges an idle session that has work in flight |

Tests: `python3 -m unittest discover -p 'test_*.py'` from this folder.

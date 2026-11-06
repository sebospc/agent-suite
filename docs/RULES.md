# Rules ready to paste

Each block below is rule text for a project's `CLAUDE.md` or `AGENTS.md`. Paste the ones the project chose, then
replace the `<...>` words. Each idea comes from gentle-ai or Engram; a project may take a block as it is, change it, or
use another tool instead. `docs/INVENTORY.md` says what each idea is and which suite part backs it.

## 1. Memory first (Engram)

```markdown
## Memory

Engram (project `<project>`, local only, cloud sync off) holds what a session needs after a restart and the lessons
that cost a lot to learn again. Decisions stay in `<decision log>`, rules in the guides.

- **Save right away**, without being asked, after a decision or convention, a bug fix (with its cause), a trap or
  surprise, a wrong measurement, or a preference of the owner you learned: `mem_save` with topic_key `rule/<topic>`,
  saying what happened, why, where, and how to apply it.
- **After every task**, ask yourself: did I decide, fix or learn something? If yes, save it now.
- **Your state** is one note, `role/<role>/state`: rewrite it at every pause with what you hold, where it stands and
  the next step. Always the same topic_key, so it updates and never makes a second copy.
- **Search first**: before a task that may have been done before, and whenever someone names past work, run
  `mem_search` with 2 to 4 distinctive words, then `mem_get_observation` for the full text.
- **After a compaction**, first `mem_session_summary` with the compacted summary (Goal, Instructions, Discoveries,
  Accomplished, Next Steps, Relevant Files), then rewrite your state, then go on.
- **A conflict**: when a save asks for a judgment, give each candidate a verdict (related, compatible, scoped, not a
  conflict, supersedes). Ask the owner only when you are unsure, or when a decision or policy would be superseded.
```

Engram conventions behind the block:

| Topic key | For |
|---|---|
| `rule/<topic>` | A rule or lesson; one key per rule, so a better version replaces the old one |
| `role/<role>/state` | Where a role stands; rewritten, never appended |
| `project/<topic>` | A fact about the project or an owner decision with its words |
| `ref/<topic>` | Where something is: a tool, an account, a path |
| `archive/role/<role>/state` | A paused role's last state, kept out of the start context |

- Pin (`mem_pin`) only what every session needs at start: the owner's standing rules and how to work with the owner.
  The start context shows each pinned memory in one line, so keep titles to one line that carries the rule.
- One store for the whole team; the role prefix in the topic key keeps one role's notes out of another's search.
- Cloud sync stays off: check no cloud target is set, and that the start hook does not set `ENGRAM_CLOUD_AUTOSYNC`.
- The memory part's hook (`engram_save_nudge.py`) reminds after 15 minutes without a save and right after a
  compaction.
- Moving from markdown memory files: `python3 tools/memory/migrate_md_memory.py MEMORY_DIR out.json --project <project>
  --pin-section "<index heading to pin>"`, read the counts it prints, then `engram import out.json`.

## 2. One recoverable doc per substantial task

```markdown
## Task docs

Small, understood work runs inline with no document. Substantial work (more than one session, more than a day, or a
decision the owner made) gets one recoverable doc: the ticket, or one file it links. It holds the owner's words
verbatim, the goal, the done criteria and the decisions taken. Every handoff and task message points at it and never
paraphrases it.
```

## 3. Delegate only for a named reason

```markdown
## Delegation

Work inline by default. Hand work to another session or a subagent only for a named reason: a wide exploration whose
file dumps would fill your context, writers working in parallel on disjoint folders, a context backstop (the next unit
of a long task goes to a fresh worker with the summary), or an independent check of a high-risk change. When in
doubt, inline.
```

## 4. Evidence budget

```markdown
## Evidence budget

A quick decision takes one batch of at most 3 tool calls and about 10k tokens of output. Bound every output: counts,
`--stat`, `tail`, a grep, a line range; never a whole file or a whole log for ten lines of it. If the batch does not
settle it, say what is still unknown and either ask or plan a real investigation.
```

## 5. Test first, per rule asked

```markdown
## Tests

For each rule the owner asked for, write one test that fails without the change, before or with the change. Each
touched existing command keeps one test that proves its old behavior. Run each new test against a mutant (the logic
removed) and report it red. No padding tests. Report real counts: `N passed, M failed, K skipped`.
```

## 6. Receipts on a frozen candidate

```markdown
## Review

Freeze the patch before any review reads it: its file is read-only, with its sha256, base, tree and patch-id. Review
depth comes from what the patch can break (data, security, a shared contract, concurrency), not from its size. The
reviewer trusts the author's receipt logs and runs only targeted checks. One scoped fix round per frozen candidate,
never a loop until clean. The landed commit must match the frozen patch (`verify_landing.py`).
```

## 7. Deterministic next step

```markdown
## Next step

A program picks the next ticket, not a model: the task queue hands each free session its next ticket in order
(`task_queue.py`, the courier). A session that finishes runs `bd ready -a <session>` and claims the top one. Nobody
picks by judgment what the queue already orders.
```

## 8. Lossless blocking prompts

```markdown
## Choices for the owner

A choice relayed to the owner keeps every option, its label and its order, with one recommendation and why. If it
cannot be shown whole, stop and say so; never drop or merge options to make it fit.
```

## 9. Skills loaded on match

```markdown
## Skills

Load a skill only when the task matches it. No new skill, plugin or MCP server in a session without the owner's yes:
each one is paid on every turn of every session.
```

## 10. Doctor, deny-list, backups

```markdown
## Safety

Back up a config before writing it, and keep the backup until the change is proved. Never print, log or commit a
secret (`.env*`, keys, tokens, `~/.ssh`). Check the setup read-only before trusting it: `python3 <suite>/tools/doctor.py
<project>`.
```

## 11. Four public states

```markdown
## Status words

To the owner, every piece of work is in one of four states: working, checking, ready, or needs you. Internals (which
session, which file, which tool) only when asked.
```

## Two layers

```markdown
## Guards

A rule broken twice gets a blocking hook, not only a line in the guide. The hooks of the agent suite cover messages,
owner questions, the panel file, unnamed saves, claims and the pause; `parts.json` lists them.
```

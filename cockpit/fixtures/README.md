# Fixtures

Real formats, trimmed. Board files come from the owner's board snapshot 3dd1d84 (Oct 15, 23:05).

| File | Source | Notes |
|---|---|---|
| `panel.json` | `~/.old-beads/panel.json` | The open ask and the last 2 answered; other top-level keys listed in `_note` |
| `dod.json` | `~/.old-beads/dod.json` | Only milestone pg-a18q (M4) |
| `goal.json` | `~/.old-beads/goal.json` | Whole file |
| `stack.json` | `~/.old-beads/stack.json` | First 3 commits |
| `beads.sample.jsonl` | `bd export --all` | 15 beads: milestones M4 and M5, criteria, found work, off-milestone work, an owner bead; descriptions and notes cut to 400 characters |
| `transcript.sample.jsonl` | a Claude Code 2.1.301 transcript | Structure and usage only; message content replaced by "[removed]". Has the repeated-usage lines that need dedupe by message.id. No compact_boundary (see `docs/DATA_SOURCES.md` for its shape) |

---
name: adopt-agent-suite
description: Adopt the agent suite in a project, part by part, or take it out again. Use when the person says "adopt agent-suite in <folder>", "set up the suite for <project>", "/adopt-agent-suite <folder>", or asks to remove the suite from a project.
---

# Adopt the agent suite in a project

The argument is the project's folder (DIR). Work from the suite's root. `parts.json` is the source for every part:
read it first, and never install a part the owner did not choose.

## 1. Look at DIR before asking

Note what DIR and the machine already have, so each question comes with a recommendation:

- tickets: a `.beads/` folder or `bd` on PATH; panes: `herdr` on PATH and `HERDR_PANE_ID`; memory: `engram` on PATH
  and an Engram MCP server in `DIR/.mcp.json` or the user settings; a status line in `DIR/.claude/settings.json`
  or `~/.claude/settings.json`; `node` 20 or newer; `gitleaks`;
- DIR's own guide (`CLAUDE.md`, `AGENTS.md`) and decision log, if it has one;
- an existing `DIR/.agent-suite.json` or `DIR/.cockpit.json` (then this is a change, not a first adoption).

## 2. Ask the owner, one part at a time

For every part in `parts.json`, in order, ask: as is, adapted, or skip. Each question says in one or two lines what
the part does, what it needs that DIR lacks, and `leaves_machine`, plus your recommendation and why. Ask with the
project's own way of asking the owner (its panel, if it has one; otherwise the chat). Keep every option whole.

- A part whose `needs.parts` the owner skipped: say so and ask again, or skip it too.
- `snapshot` sends data off the machine: it needs the owner's explicit yes and a private repo the owner made.
- `adapted` means the owner wants a change: write down what, in their words, before going on.

## 3. Check the prerequisites

For each chosen part, check `needs.bins` on PATH and `needs.env` set. A missing one: tell the owner what to install,
or change the choice. Never install a tool or a seat without the owner's yes.

## 4. Write the project config

Write `DIR/.agent-suite.json` (keys and defaults: `tools/team/suite_config.py`):

- `board_dir`: where the board files live (panel, task queue, slots, logs), outside the repo.
- `session_prefix`, `lead`, `coordinator`: how DIR's sessions are named.
- `slots`: the named resources DIR shares (a simulator, a heavy build, a test database), each `{"minutes": N}`.
- `engram_project`, `team_json`, `courier`, `team_check`, `snapshot` as chosen.
- `parts`: every part with `as-is`, `adapted` or `skip`.

`examples/first-project/.agent-suite.json` is one real config. Show the file to the owner and wait for a yes: the
next steps change `DIR/.claude/settings.json`.

## 5. Install

1. Cockpit chosen: run the cockpit-setup skill (`cockpit/.claude/skills/cockpit-setup/SKILL.md`) with DIR.
2. `python3 tools/install_team.py install DIR`. It backs up `DIR/.claude/settings.json`, then wraps the hooks of
   the chosen parts. A second run changes nothing; after a changed choice it swaps only the suite's entries.
3. The manual steps in each chosen part's `install`:
   - launcher: `BOARD/team.json` from `templates/team.json` (one entry per session: model, effort, window, launch,
     template, role, writes); `AGENT_SUITE` set to the suite's folder; the shell wrapper from `templates/shell/`.
   - protocol: one prompt per session from `templates/roles/`, with `{{session}}`, `{{folders}}` and
     `{{decision_log}}` filled in, saved where DIR keeps its session prompts.
   - rules and memory: paste the chosen blocks of `docs/RULES.md` into DIR's guide, with `<project>` replaced.
   - queue: start the courier detached and keep its pid. team-check: a timer every 20 minutes.

## 6. Verify

`python3 tools/doctor.py DIR` must end with `doctor: ok` (`warn` lines are optional features left off). Then run each
chosen part's `verify` and report what it printed. Report real numbers, never "it works".

## 7. Record the choices

`DIR/.agent-suite.json` already holds every choice. If DIR keeps a decision log, add one line with the date, the parts
chosen, skipped and adapted, and the owner's words for each adapted one.

## Take it out

1. `python3 tools/install_team.py uninstall DIR`. The settings come back byte for byte; if DIR changed them after the
   install, only the suite's entries go and the backup stays next to the file.
2. Cockpit installed: the cockpit-setup skill's uninstall step.
3. Each chosen part's `uninstall` (stop the courier, remove the timer, the wrapper, the pasted blocks).
4. Ask the owner whether to delete `DIR/.agent-suite.json` and the board folder; never delete them without a yes.

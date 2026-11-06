# agent-suite

Tools for running a team of long-lived coding agent sessions on one machine: a cockpit page with an autopilot that
manages each session's tokens, guards on messages and owner questions, a task queue with one ticket per session,
named resource slots, a memory layer on Engram, and rule text ready to paste. A project takes each part as is,
adapted, or not at all. Nothing here names a project; each project's choices live in its own folder.

## Map

| Path | What |
|---|---|
| `parts.json` | Every part: what it does, what it needs, its config keys, install, verify and uninstall commands, what leaves the machine |
| `docs/INVENTORY.md` | What each part is for, and where each gentle-ai idea is in the suite |
| `docs/PROTOCOL.md` | Roles, message types, the lead-coordinator flow, review by risk |
| `docs/RULES.md` | Rule text ready to paste, one block per idea, and the Engram conventions |
| `cockpit/` | The cockpit and its autopilot (`cockpit/README.md`) |
| `tools/team/` | The team tools and hooks; `.agent-suite.json` in the project configures them (`tools/team/suite_config.py`) |
| `tools/install_team.py`, `tools/doctor.py` | Wrap the chosen hooks into a project, take them out byte for byte, check an adoption read-only |
| `tools/memory/` | Migration from markdown memory files to Engram |
| `templates/` | Role prompts, the `team.json` format, the claude shell wrappers |
| `examples/first-project/` | One real project's choices and configs |

## Adopt the suite in a project

Run this flow when told "adopt agent-suite in DIR". The skill `.claude/skills/adopt-agent-suite/` holds the same
steps in detail.

1. Read `parts.json`. For each part, ask the owner: as is, adapted, or skip. Say what it needs and whether anything
   leaves the machine. Recommend from what DIR already has (beads, herdr, Engram, a status line).
2. Check the prerequisites of the chosen parts (`needs` in `parts.json`): bins on PATH, env keys, the parts they need.
3. Write `DIR/.agent-suite.json`: the board folder, the session prefix, the lead and coordinator roles, the slots,
   the snapshot remote if chosen, and `parts` with every choice. Show it to the owner before going on.
4. Cockpit chosen: run the cockpit-setup skill (`cockpit/.claude/skills/cockpit-setup/`), which writes
   `DIR/.cockpit.json` and wraps the status line and pause guard.
5. `python3 tools/install_team.py install DIR`: wraps the chosen hooks into `DIR/.claude/settings.json` after a
   backup. A second run changes nothing.
6. The parts with a manual step (`install` in `parts.json`): the shell wrapper, `team.json`, the courier, the team
   check timer, the role prompts, the pasted rules.
7. `python3 tools/doctor.py DIR` must print `doctor: ok`. Then run each chosen part's `verify`.
8. Record the choices in DIR: `.agent-suite.json` holds them; add one line per part to DIR's decision log if it has
   one, with the owner's words.

Uninstall: `python3 tools/install_team.py uninstall DIR`, then `python3 cockpit/tools/install_project.py uninstall
DIR` if the cockpit was installed, then each part's `uninstall` step. The settings file comes back byte for byte.

## Rules for changes to the suite

- No project name in suite code or docs: `python3 tools/check_no_project_names.py` must pass (names in the
  git-ignored `.project-names`).
- Python standard library only. Every logic change leaves a test that fails without it. Report real counts.
- Tests: `python3 -m unittest discover -p 'test_*.py'` in each of `tools/`, `tools/team/` and `tools/memory/`;
  `python3 -m unittest discover -s tests -t .` in `cockpit/`.

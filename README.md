# agent-suite

Tools for running a team of long-lived coding agent sessions on one machine: a cockpit page, an autopilot that manages each session's tokens, guards on messages and owner questions, a memory layer, and a config per project. Each project picks what it uses.

Start with `docs/INVENTORY.md`: every part, what it does, and which gentle-ai ideas and Engram habits a project can take as they are, adapted, or replace with another tool.

## Layout

| Path | What |
|---|---|
| `docs/` | The inventory and how-tos |
| `tools/` | Suite scripts; `check_no_project_names.py` fails when a project name leaks into suite code or docs |
| `cockpit/` | The cockpit and its autopilot: `cockpit/README.md`, tests with `python3 -m unittest discover -s tests -t .` from that folder |
| `board/`, `beads/`, `memory/` | One project's working state, written by its board snapshot after every push. Project data, so the names check skips these three folders |

## Project names

List the names to keep out of the suite in `.project-names`, one per line. The file is git-ignored, so the names never enter the repo. Then run `python3 tools/check_no_project_names.py`.

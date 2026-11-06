# agent-suite

Tools for running a team of long-lived coding agent sessions on one machine: a cockpit page, an autopilot that manages
each session's tokens, guards on messages and owner questions, a task queue, named resource slots, a memory layer, and
a config per project. Each project picks what it uses.

Start at `AGENTS.md`: the map of parts and how to adopt the suite in a project. In Claude Code, say "adopt agent-suite
in DIR" from this folder and the adopt skill runs the flow.

## Project names

List the names to keep out of the suite in `.project-names`, one per line. The file is git-ignored, so the names never
enter the repo. Then run `python3 tools/check_no_project_names.py`.

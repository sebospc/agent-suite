---
name: cockpit-setup
description: Adapt the cockpit to another project, or take it out again. Use when the person says "set up the cockpit for <project>", "adapt the cockpit to <folder>", "/cockpit-setup <folder>", or asks to remove the cockpit from a project.
---

# Set up the cockpit for a project

The argument is the project's folder (call it DIR). Work from the cockpit repo's root.

1. Write `DIR/.cockpit.json`. Start from this repo's `.cockpit.json` (the project's) and change what differs:
   - `port`: a free one if the project's cockpit runs at the same time.
   - `paths.repo`, `paths.repos`: DIR and every repo the project's sessions commit to.
   - `paths.usage`, `paths.pause_file`, the logs: under a folder of this project, never the project's.
   - `team.roles`, `team.coordinating`: the project's sessions, as they are named in the panes.
   - Leave out what the project does not have: `paths.board_dir` with `paths.bd_command` (no beads), `paths.panel`
     with `paths.ask_owner` (no panel of asks; then `paths.gate_logs` must be a folder), `paths.milestone_dir` (no
     `dod.json` and `goal.json`). The cockpit starts without them and leaves those sections off the page.
   - Keys that are the same for every project on this machine (transcripts, herdr, node, rtk) can go in
     `~/.config/cockpit/config.json` instead; the project's file wins over it.
2. Show the person the file and ask before the next step: it changes `DIR/.claude/settings.json`.
3. Run `python3 tools/install_project.py install DIR`. It checks the config first (an unknown key, a wrong type or a
   missing key stops it with one line), backs `DIR/.claude/settings.json` up, then wraps the status line and adds the
   pause guard. Running it again changes nothing.
4. Start it: `python3 cockpit.py --project DIR`. Report the url it prints and any source the header lists as broken.

To take it out: `python3 tools/install_project.py uninstall DIR`. The settings file comes back byte for byte; if the
project changed it after the install, only the cockpit's entries go and the backup stays next to it.

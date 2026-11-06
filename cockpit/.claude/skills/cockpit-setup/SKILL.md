---
name: cockpit-setup
description: Adapt the cockpit to another project, or take it out again. Step 5.1 of the suite's adopt-agent-suite skill; use it alone when the person says "set up the cockpit for <project>", "adapt the cockpit to <folder>", "/cockpit-setup <folder>", or asks to remove the cockpit from a project.
---

# Set up the cockpit for a project

The argument is the project's folder (call it DIR). Work from the cockpit folder (`cockpit/` in the suite). When the
whole suite is being adopted, the adopt skill (`.claude/skills/adopt-agent-suite/` at the suite's root) calls this
step; the owner already chose the cockpit there.

1. Write `DIR/.cockpit.json`. Start from this folder's `.cockpit.json` (neutral; `{project}` is DIR and `{suite}` the
   suite's folder, so most paths need no change) and change what differs:
   - `port`: a free one if another project's cockpit runs at the same time.
   - `paths.repos`: DIR and every other repo the project's sessions commit to; `paths.landing_ref`: the branch or ref
     the lead lands on; `paths.decision_log`: the owner's decision log, if DIR has one.
   - `paths.usage`, `paths.pause_file`, the logs: under a folder of this project, never another project's.
   - `team.roles`, `team.coordinating`, `team.lead`, `team.coordinator`, `team.session_prefix`: the project's
     sessions as named in the panes (the same names as in `DIR/.agent-suite.json`).
   - Leave out what the project does not have: `paths.board_dir` with `paths.bd_command` (no beads), `paths.panel`
     with `paths.ask_owner` (no panel of asks; then `paths.gate_logs` must be a folder), `paths.milestone_dir` (no
     `dod.json` and `goal.json`). The cockpit starts without them and leaves those sections off the page.
   - Keys that are the same for every project on this machine (transcripts, herdr, node, rtk) can go in
     `~/.config/cockpit/config.json` instead; the project's file wins over it.
   - One real config: `examples/first-project/.cockpit.json` at the suite's root.
2. Show the person the file and ask before the next step: it changes `DIR/.claude/settings.json`.
3. Run `python3 tools/install_project.py install DIR`. It checks the config first (an unknown key, a wrong type or a
   missing key stops it with one line), backs `DIR/.claude/settings.json` up, then wraps the status line and adds the
   pause guard. Running it again changes nothing.
4. Start it: `python3 cockpit.py --project DIR`. Report the url it prints and any source the header lists as broken.

To take it out: `python3 tools/install_project.py uninstall DIR`. The settings file comes back byte for byte; if the
project changed it after the install, only the cockpit's entries go and the backup stays next to it.

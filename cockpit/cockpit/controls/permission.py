from typing import Optional, Tuple

from cockpit.controls.commands import COMMANDS
from cockpit.controls.permission_rules import EFFORTS, KINDS, clear_permission

__all__ = ["EFFORTS", "KINDS", "clear_permission", "command_for"]


def command_for(kind: str, row: dict, level: str = "") -> Tuple[Optional[str], str]:
    """(text to type into the session's pane, or None with the reason it is not allowed now). The rules are
    docs/REQUIREMENTS.md "Controls"; each control's own rule is its command in cockpit/controls/commands.py."""
    if row["state"] == "off" or not row["pane"]:
        return None, f"{row['name']} is not running in a herdr pane."
    if kind in ("compact", "clear") and row.get("background"):
        return None, f"Its pane shows {row['background']} running; a {kind} now drops what it reports back to. Wait until it finishes."
    command = COMMANDS.get(kind)
    return command.text(row, level) if command else (None, f"Unknown control {kind}.")

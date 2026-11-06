#!/usr/bin/env python3
# PreToolUse on Edit, Write and Bash: only ask_owner.py writes the panel file, in its own format, so an ask is never lost
# or rewritten by hand (root CLAUDE.md rule 10; panel.json was rewritten with json.dump twice). Fails open on any error.
import json
import os
import re
import sys

PANEL = os.path.realpath(os.environ.get("AGENT_PANEL", os.path.expanduser("~/.agent-board/panel.json")))
PANEL_NAME = re.escape(os.path.basename(PANEL))
WRITES_IN_SHELL = re.compile(
    rf"json\.dump|write_text|\.write\(|open\([^)]*['\"][wa]\+?['\"]|sed\s+-i|perl\s+-\w*i|\btee\b|>\s*\S*{PANEL_NAME}"
    rf"|\b(?:mv|cp)\s+\S+\s+\S*{PANEL_NAME}")
PANEL_TOOL = re.compile(r"\bask_owner\.py\b")
REASON = ("panel_write_guard: only ask_owner.py writes the panel (root CLAUDE.md rule 10). Add with `python3 "
          "~/.agent-board/ask_owner.py add ...`, record an answer with `... answer <id> \"<owner's words>\"`.")


def verdict(hook: dict) -> str | None:
    tool_input = hook.get("tool_input") or {}
    if hook.get("tool_name") in ("Edit", "Write", "MultiEdit"):
        path = tool_input.get("file_path")
        return REASON if isinstance(path, str) and os.path.realpath(os.path.expanduser(path)) == PANEL else None
    command = tool_input.get("command") if hook.get("tool_name") == "Bash" else None
    if not isinstance(command, str) or not re.search(PANEL_NAME, command) or PANEL_TOOL.search(command):
        return None
    return REASON if WRITES_IN_SHELL.search(command) else None


def main() -> int:
    try:
        reason = verdict(json.load(sys.stdin))
    except Exception:  # noqa: BLE001
        return 0
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

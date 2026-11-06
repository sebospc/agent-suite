# PreToolUse hook (tools/install_project.py): while the cockpit's pause file exists, a session commits and pushes
# nothing. Exit 2 blocks the call and shows the reason to the session.
import json
import os
import re
import sys

# One shell command per segment, so "git log; echo push" is not read as a push.
SEGMENT = re.compile(r"[^;&|\n]+")
COMMIT_OR_PUSH = re.compile(r"\bgit\b.*\b(commit|push)\b")


def blocked(hook: dict) -> bool:
    command = (hook.get("tool_input") or {}).get("command") or ""
    return hook.get("tool_name") == "Bash" and any(COMMIT_OR_PUSH.search(part) for part in SEGMENT.findall(command))


def main(argv) -> int:
    if not os.path.exists(os.path.expanduser(argv[1])):
        return 0
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return 0
    if blocked(hook):
        print(f"The team is paused ({argv[1]} exists): no commit or push until the owner resumes it.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""PreToolUse hook on Bash: one ticket in progress per session, as a hard block on the claim itself.

A claim (`bd update ID --claim`, `bd claim ID`, `--status in_progress`) is denied when the session already holds a
different ticket, in the task queue or as an in_progress bead. The session is the command's BEADS_ACTOR=, else the
AGENT_SESSION or BEADS_ACTOR the launcher exported. With no session known the claim passes: the guard never guesses.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import suite_config  # noqa: E402
import task_queue  # noqa: E402

SEGMENT = re.compile(r"[^;&|\n]+")
CLAIM = re.compile(r"\bbd\s+(?:claim\s+(?P<a>\S+)|update\s+(?P<b>\S+)\s.*(?:--claim\b|(?:--status|-s)[= ]in_progress\b))")
ACTOR = re.compile(r"\bBEADS_ACTOR=([\w.-]+)")


def claimed(command: str):
    for segment in SEGMENT.findall(command):
        match = CLAIM.search(segment)
        if match:
            return match.group("a") or match.group("b"), segment
    return None, None


def in_progress_beads(session: str, board_dir: str) -> list:
    out = subprocess.run(["bd", "list", "--status", "in_progress", "--assignee", session, "--json"],
                         capture_output=True, text=True, cwd=os.path.expanduser(board_dir)).stdout
    return [bead["id"] for bead in json.loads(out or "[]")]


def denial(hook: dict, config: dict, beads_of=in_progress_beads):
    if hook.get("tool_name") != "Bash":
        return None
    bead, segment = claimed(str((hook.get("tool_input") or {}).get("command", "")))
    if not bead:
        return None
    actor = ACTOR.search(segment)
    session = actor.group(1) if actor else os.environ.get("AGENT_SESSION") or os.environ.get("BEADS_ACTOR")
    if not session:
        return None
    held = task_queue.holder(task_queue.read(task_queue.in_flight_path(config)), session)
    if held and held != bead:
        return f"{session} holds {held} in the task queue"
    others = [other for other in beads_of(session, config["board_dir"]) if other != bead]
    if others:
        return f"{session} already has {', '.join(others)} in progress"
    return None


def main() -> int:
    try:
        reason = denial(json.load(sys.stdin), suite_config.load())
    except Exception:  # noqa: BLE001 - only exit 2 blocks; a crash must never be how this hook blocks
        return 0
    if not reason:
        return 0
    print(f"Claim denied: {reason}. One ticket in progress per session: finish it, or move it to waiting "
          "(task_queue.py wait) first.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

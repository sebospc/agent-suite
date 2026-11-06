#!/usr/bin/env python3
# Engram's own save reminders as our hooks (owner panel 206f88, ported from its Claude Code plugin, local only):
# a prompt 15 minutes past the session's last save, and a SessionStart right after a compaction.
import json
import os
import sys
import time
from datetime import datetime

from transcript_tail import tail_lines
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

TAIL_BYTES = 3_000_000
QUIET_SECONDS = 900
SAVE_TOOLS = ("mcp__engram__mem_save", "mcp__engram__mem_update", "mcp__engram__mem_session_summary")
NUDGED = suite_config.board_file("AGENT_ENGRAM_NUDGED", "engram-nudged")

NUDGE = ("MEMORY REMINDER: 15 minutes or more since this session's last Engram save. "
         "If you decided, fixed or learned something, or your state moved, mem_save it now "
         "(topic_key role/<role>/state or rule/<topic>).")
AFTER_COMPACTION = ("AFTER COMPACTION: first call mem_session_summary{project} with "
                    "the compacted summary above (Goal, Instructions, Discoveries, Accomplished, Next Steps, Relevant Files), "
                    "then rewrite your role/<role>/state, then go on.")


def after_compaction() -> str:
    try:
        project = suite_config.load()["engram_project"]
    except suite_config.ConfigError:
        project = ""
    return AFTER_COMPACTION.format(project=f" in project {project}" if project else "")


def epoch(timestamp: str) -> float:
    return datetime.fromisoformat(timestamp).timestamp()


def is_save(entry: dict) -> bool:
    content = entry.get("message", {}).get("content")
    return isinstance(content, list) and any(
        part.get("type") == "tool_use" and part.get("name") in SAVE_TOOLS for part in content if isinstance(part, dict))


def last_save_or_start(lines: list[str]) -> float | None:
    # Engram saves carry no session id, so the transcript tells. No save in the tail: its first moment stands in.
    first_seen = last_save = None
    for line in lines:
        if first_seen is None or any(tool in line for tool in SAVE_TOOLS):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not entry.get("timestamp"):
                continue
            first_seen = first_seen or epoch(entry["timestamp"])
            if is_save(entry):
                last_save = epoch(entry["timestamp"])
    return last_save or first_seen


def nudged_recently(session_id: str, now: float) -> bool:
    marker = os.path.join(NUDGED, session_id)
    try:
        with open(marker) as last_nudge:
            if now - float(last_nudge.read()) < QUIET_SECONDS:
                return True
    except (OSError, ValueError):
        pass
    os.makedirs(NUDGED, exist_ok=True)
    with open(marker, "w") as written:
        written.write(str(now))
    return False


def context_for(event: dict, now: float) -> str | None:
    if event.get("hook_event_name") == "SessionStart":
        return after_compaction() if event.get("source") == "compact" else None
    since = last_save_or_start(tail_lines(event["transcript_path"], TAIL_BYTES))
    if since is None or now - since < QUIET_SECONDS or nudged_recently(event.get("session_id", "unknown"), now):
        return None
    return NUDGE


def main() -> None:
    try:
        event = json.load(sys.stdin)
        context = context_for(event, time.time())
    except (OSError, ValueError, KeyError, AttributeError, TypeError):  # A reminder must never block a prompt.
        context = None
    if context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event["hook_event_name"], "additionalContext": context}}))


if __name__ == "__main__":
    main()

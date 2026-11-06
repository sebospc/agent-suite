#!/usr/bin/env python3
# Stop hook: a reply that asks the owner something may end only after the
# question is on the panel. Questions asked only in a session window got lost on 2026-10-14.
import json
import os
import re
import sys

from transcript_tail import tail_lines
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

ASK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ask_owner.py")

# The last turn is recent: a full read of a 1 GB transcript took 18.6 s, over the 10 s timeout (2026-11-05).
TAIL_BYTES = 5_000_000
PANEL = suite_config.board_file("AGENT_PANEL", "panel.json")
ASK_CALL = re.compile(r"^\s*(env [^;|&]*\s)?python3?\s+\S*ask_owner\.py\s+(add|answer)\b")
# A reply may point at an ask already on the panel instead of adding it again.
ASK_ID = re.compile(r"\b(?:ask|panel)\b[^\n]{0,40}?\b([0-9a-f]{6})\b", re.IGNORECASE)
OWNER_DECISION = re.compile(
    r"\b(your call|you decide|do you want|should i|which (one|ones) should|pick for you)\b",
    re.IGNORECASE,
)
# A request worded as a command slips past the question mark: "Next: reply yes if I should..." (2026-11-06).
OWNER_REQUEST = re.compile(
    r"\bnext:\s*(reply|answer|tell me|run|confirm|approve|say|pick|choose|look at|open)\b"
    r"|\breply (yes|no|with|[\"'“]|[abc]\b)|\btell me (if|whether|which|what|when)\b|\bif you want\b",
    re.IGNORECASE,
)
QUESTION_END = re.compile(r"\?(\s|$)")
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
NOT_THE_OWNER = (
    "<cross-session-message",
    "Another Claude session sent a message",
    "[Cross-session delivery notice]",
    "[Cross-session idle notice]",
    "<task-notification",
    "<system-reminder",
    "<artifact-content-authored-by-others",
    "TEAM CHECK",
    "Your previous turn was cut off",
)


def blocks(entry: dict) -> list:
    content = entry.get("message", {}).get("content", "")
    return [{"type": "text", "text": content}] if isinstance(content, str) else content


def starts_turn(entry: dict) -> bool:
    if entry.get("type") != "user":
        return False
    return any(block.get("type") == "text" for block in blocks(entry))


def is_from_owner(entry: dict) -> bool:
    text = " ".join(block.get("text", "") for block in blocks(entry) if block.get("type") == "text")
    return not text.lstrip().startswith(NOT_THE_OWNER)


def last_turn(entries: list) -> list:
    starts = [index for index, entry in enumerate(entries) if starts_turn(entry)]
    return entries[starts[-1]:] if starts else entries


def asks_owner(text: str) -> bool:
    prose = CODE.sub("", text)
    return bool(QUESTION_END.search(prose) or OWNER_DECISION.search(prose) or OWNER_REQUEST.search(prose))


def panel_ids(panel_path: str) -> set:
    try:
        with open(panel_path, encoding="utf-8") as panel_file:
            panel = json.load(panel_file)
    except (OSError, ValueError):
        return set()
    # Asks answered before ids existed have none.
    return {ask["id"] for ask in panel.get("asks", []) + panel.get("answered", []) if "id" in ask}


def verdict(entries: list, known_ask_ids: set) -> str | None:
    turn = last_turn(entries)
    if not turn or not is_from_owner(turn[0]):
        return None
    assistant_blocks = [block for entry in turn if entry.get("type") == "assistant" for block in blocks(entry)]
    texts = [block.get("text", "") for block in assistant_blocks if block.get("type") == "text"]
    commands = [
        block.get("input", {}).get("command", "")
        for block in assistant_blocks
        if block.get("type") == "tool_use" and block.get("name") == "Bash"
    ]
    asking_texts = [text for text in texts if asks_owner(text)]
    if not asking_texts or any(ASK_CALL.search(command) for command in commands):
        return None
    named_ids = {match.group(1) for text in texts for match in ASK_ID.finditer(text)}
    if named_ids & known_ask_ids:
        return None
    return (
        "This turn asks the owner something that is not on the panel. "
        "Add it with `python3 " + ASK + " add ...` and name its id in the reply, "
        "or rewrite the reply so it asks nothing."
    )


def parsed_entries(lines: list[str]) -> list:
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def main() -> int:
    hook = json.load(sys.stdin)
    # No stop_hook_active bypass: the session can always satisfy the guard by adding the ask or rewording.
    entries = parsed_entries(tail_lines(hook["transcript_path"], TAIL_BYTES))
    reason = verdict(entries, panel_ids(PANEL))
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

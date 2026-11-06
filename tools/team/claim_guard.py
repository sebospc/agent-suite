#!/usr/bin/env python3
# Stop hook: a reply that claims it saved, landed, committed or pushed something names it (a sha, a bead,
# a file), so the owner can check it. An action claim ("I saved", "Landed."), not the adjective ("the landed commit").
# Each block is one JSON line in the saved-guard log (AGENT_SAVED_LOG), which the cockpit's "said vs saved" reads.
import json
import os
import re
import sys
import time

from owner_ask_guard import CODE, TAIL_BYTES, blocks, last_turn, parsed_entries
from transcript_tail import tail_lines
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

CLAIM = re.compile(r"(?:^|[.!:]\s+|\b(?:I|we|brain|it|both)\s+(?:have\s+|has\s+|just\s+)?)(?:saved|landed|committed|pushed)\b",
                   re.IGNORECASE | re.MULTILINE)
# A bead id is a short prefix, a dash and an id with a digit in it (t-12, ab-3k9x.2), so "follow-up" is not one.
NAMED = re.compile(r"\b[0-9a-f]{7,40}\b|\b[a-z]{1,8}-(?=[0-9a-z.]*\d)[0-9a-z]{2,}(?:\.[0-9a-z]+)*\b"
                   r"|[\w./~-]+\.(?:md|json|py|patch|msg|txt|html)\b")
SAVED_LOG = suite_config.board_file("AGENT_SAVED_LOG", "saved_guard.jsonl")


def reply_text(entries: list) -> str:
    return "\n".join(block.get("text", "") for entry in last_turn(entries) if entry.get("type") == "assistant"
                     for block in blocks(entry) if block.get("type") == "text")


def verdict(entries: list) -> str | None:
    reply = reply_text(entries)
    if not CLAIM.search(CODE.sub("", reply)) or NAMED.search(reply):
        return None
    return ("This reply says something was saved, landed, committed or pushed but names no sha, bead or file. "
            "Name it (\"landed in <sha>\", \"saved to <file>\"), or drop the claim.")


def log_block(text: str) -> None:
    entry = {"t": int(time.time()), "session": os.environ.get("AGENT_SESSION", ""), "text": text}
    try:
        with open(SAVED_LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # a log that can't be written must not change the verdict


def main() -> int:
    try:
        hook = json.load(sys.stdin)
        # Held once: a second stop of the same turn goes through, so a claim with nothing to name never loops.
        if hook.get("stop_hook_active"):
            return 0
        entries = parsed_entries(tail_lines(hook["transcript_path"], TAIL_BYTES))
        reason = verdict(entries)
    except Exception:  # noqa: BLE001
        return 0
    if reason:
        log_block(reply_text(entries)[:300])
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

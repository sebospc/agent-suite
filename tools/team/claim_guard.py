#!/usr/bin/env python3
# Stop hook (mb-5558): a reply that claims it saved, landed, committed or pushed something names it (a sha, a bead,
# a file), so the owner can check it. An action claim ("I saved", "Landed."), not the adjective ("the landed commit").
import json
import re
import sys

from owner_ask_guard import CODE, TAIL_BYTES, blocks, last_turn, parsed_entries
from transcript_tail import tail_lines

CLAIM = re.compile(r"(?:^|[.!:]\s+|\b(?:I|we|brain|it|both)\s+(?:have\s+|has\s+|just\s+)?)(?:saved|landed|committed|pushed)\b",
                   re.IGNORECASE | re.MULTILINE)
NAMED = re.compile(r"\b[0-9a-f]{7,40}\b|\b(?:mb|pg)-[0-9a-z]+(?:\.[0-9a-z]+)*\b|[\w./~-]+\.(?:md|json|py|patch|msg|txt|html)\b")


def verdict(entries: list) -> str | None:
    texts = [block.get("text", "") for entry in last_turn(entries) if entry.get("type") == "assistant"
             for block in blocks(entry) if block.get("type") == "text"]
    reply = "\n".join(texts)
    if not CLAIM.search(CODE.sub("", reply)) or NAMED.search(reply):
        return None
    return ("This reply says something was saved, landed, committed or pushed but names no sha, bead or file. "
            "Name it (\"landed in <sha>\", \"saved to <file>\"), or drop the claim.")


def main() -> int:
    try:
        hook = json.load(sys.stdin)
        # Held once: a second stop of the same turn goes through, so a claim with nothing to name never loops.
        if hook.get("stop_hook_active"):
            return 0
        reason = verdict(parsed_entries(tail_lines(hook["transcript_path"], TAIL_BYTES)))
    except Exception:  # noqa: BLE001
        return 0
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

import hashlib
import re
from typing import Optional

PEER_PREFIX = "<cross-session-message"  # the receiver's line for a message from another session (DATA_SOURCES.md)
PEER_WRAPPER = "Another Claude session sent a message:"  # Claude Code puts it before the tag; since 2026-10-11 on almost every one
PEER_BODY = re.compile(r"<cross-session-message[^>]*>(.*?)(?:</cross-session-message>|$)", re.S)
COMMAND = re.compile(r"^\s*(?:<command-name>|/[a-z])")
# the project's docs/WORKFLOW.md "Messages": line 1 is `<TYPE> <bead> [vN]`, at most 10 lines.
TYPES = {"TASK", "GO-REQ", "GO", "HOLD", "VERIFY-REQ", "VERIFIED", "SEC-REQ", "SEC", "LAND-READY", "LANDED", "PUSHED",
         "SLOT-REQ", "SLOT-FREE", "BLOCKED", "RULING-REQ", "RULING", "BOUNCE"}
FIRST_LINE = re.compile(r"^([A-Z][A-Z-]+)\s+((?:pg|mb)-[a-z0-9]{3,5}(?:\.\d+)*)(?:\s+v\d+)?\s*$")
MAX_LINES = 10
RECEIPT_KEYS = ("sha256", "sha", "base", "tree", "go-tree", "patch")  # what ties a review to the exact patch (WORKFLOW table)
# Before 2026-10-14 a GO or HOLD named its patch on line 1 in free text: "GO pg-x v3 (4ba05a81) on ..", "GO on pg-x v1, sha256 07fa1dc6".
LOOSE_SHA256 = re.compile(r"(?:\(|sha256[:\s]+)([0-9a-f]{7,64})\b")


def text_of(message: dict) -> Optional[str]:
    """The typed text of a user line; None for a tool result, which continues a turn rather than starting one."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    texts = [b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(texts) if texts else None


def prompt_of(message: dict, stamp: Optional[float]) -> Optional[dict]:
    """Who started a turn: another session's message, a slash command (the owner's control or the autopilot), or
    the person typing. A peer message also carries what the format check and the duplicate count need."""
    text = text_of(message)
    if text is None:
        return None
    if text.lstrip().removeprefix(PEER_WRAPPER).lstrip().startswith(PEER_PREFIX):
        match = PEER_BODY.search(text)
        body = (match.group(1) if match else "").strip()
        lines = body.splitlines()
        first = FIRST_LINE.match(lines[0].strip()) if lines else None
        kind, bead = (first.group(1), first.group(2)) if first else ("", "")
        head = lines[0].split()[0] if lines and lines[0].split() else ""
        keys = receipt_keys(lines[1:])
        loose_sha = LOOSE_SHA256.search(lines[0]) if lines and not first else None
        if loose_sha and "sha256" not in keys:
            keys["sha256"] = loose_sha.group(1)
        return {"t": stamp or 0.0, "origin": "peer", "type": kind if kind in TYPES else "", "bead": bead,
                "head": head if head in TYPES else "", "in_format": bool(first) and kind in TYPES and len(lines) <= MAX_LINES,
                "digest": hashlib.sha256(body.encode("utf-8")).hexdigest()[:12], "keys": keys, "chars": len(text)}
    if COMMAND.match(text):
        return {"t": stamp or 0.0, "origin": "command", "chars": len(text)}
    # Heuristic: harness lines (a task notification, a hook's reminder) open with a tag; a person types plain text.
    return {"t": stamp or 0.0, "origin": "own" if text.lstrip().startswith("<") else "person", "chars": len(text)}


def review_request_of(text: str) -> Optional[dict]:
    """A GO-REQ as its sender wrote it (the receiver's line is prompt_of's): its bead and sha256."""
    lines = text.strip().splitlines()
    first = FIRST_LINE.match(lines[0].strip()) if lines else None
    if not first or first.group(1) != "GO-REQ":
        return None
    return {"bead": first.group(2), "sha256": receipt_keys(lines[1:]).get("sha256", "")}


def receipt_keys(lines) -> dict:
    found = {}
    for line in lines:
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in RECEIPT_KEYS and value.strip():
            found[key] = value.strip().split()[0].lower()
    return found

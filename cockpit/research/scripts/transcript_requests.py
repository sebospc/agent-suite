"""Read Claude Code transcripts into deduplicated requests and events, for the phase 0 scripts.

Keeps only numbers, times, model names and the account email (used for attribution, never printed).
Python 3.9 compatible: the owner's Mac may run the system python3.
"""
import glob
import json
import os
import re
from datetime import datetime

READ_TOOLS = {"Read", "Grep", "Glob"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def address_in(text):
    """userEmail holds a sentence ("The user's email address is X. Use it only ..."), not a bare address."""
    found = EMAIL.search(text) if isinstance(text, str) else None
    return found.group(0).rstrip(".") if found else None


def parse_time(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def transcript_paths(roots):
    paths = set()
    for root in roots:
        paths.update(glob.glob(os.path.join(os.path.expanduser(root), "**", "*.jsonl"), recursive=True))
    return sorted(paths)


def is_subagent_file(path):
    return os.sep + "subagents" + os.sep in path


def parent_session_id(path):
    """A subagent file lives in <session-id>/subagents/; its account is its parent's."""
    if is_subagent_file(path):
        return os.path.basename(os.path.dirname(os.path.dirname(path)))
    return os.path.splitext(os.path.basename(path))[0]


def _tool_targets(message):
    targets = []
    for block in message.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            given = block.get("input") or {}
            target = given.get("file_path") or given.get("path") or given.get("pattern")
            targets.append((block.get("name"), target))
    return targets


def read_transcript(path):
    """One file: requests deduped by message.id (a response is written as up to 4 lines repeating
    its usage), plus compact boundaries, titles and the account email over time."""
    requests, boundaries, titles, emails = {}, [], [], []
    try:
        handle = open(path, encoding="utf-8")
    except OSError:
        return {"requests": [], "boundaries": [], "titles": [], "emails": []}
    with handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            kind = entry.get("type")
            stamp = parse_time(entry.get("timestamp"))
            if kind == "system" and (entry.get("subtype") == "compact_boundary" or "compactMetadata" in entry):
                meta = entry.get("compactMetadata") or {}
                boundaries.append({"t": stamp, "trigger": meta.get("trigger"),
                                   "pre": meta.get("preTokens"), "post": meta.get("postTokens")})
            elif kind == "custom-title" and entry.get("customTitle"):
                titles.append(entry["customTitle"])
            elif kind == "attachment":
                email = address_in(((entry.get("attachment") or {}).get("context") or {}).get("userEmail"))
                if email and stamp is not None:
                    emails.append((stamp, email))
            elif kind == "assistant":
                _add_request(requests, entry, stamp)
    rows = sorted(requests.values(), key=lambda r: r["t_first"] or 0)
    for row in rows:
        _finish(row)
    return {"requests": rows, "boundaries": boundaries, "titles": titles, "emails": sorted(emails)}


def _add_request(requests, entry, stamp):
    message = entry.get("message") or {}
    usage = message.get("usage") or {}
    if not usage or message.get("model") in (None, "<synthetic>"):
        return
    key = message.get("id") or entry.get("requestId")
    row = requests.get(key)
    if row is None:
        row = requests[key] = {"model": message.get("model"), "effort": entry.get("effort"),
                               "sidechain": bool(entry.get("isSidechain")), "t_first": stamp,
                               "t_last": stamp, "usage": usage, "tools": []}
    if stamp is not None:
        row["t_first"] = stamp if row["t_first"] is None else min(row["t_first"], stamp)
        row["t_last"] = stamp if row["t_last"] is None else max(row["t_last"], stamp)
    # Streamed blocks repeat the input side; the last block carries the final output count.
    if (usage.get("output_tokens") or 0) >= (row["usage"].get("output_tokens") or 0):
        row["usage"] = usage
    row["tools"].extend(_tool_targets(message))


def _finish(row):
    usage = row.pop("usage")
    split = usage.get("cache_creation") or {}
    row["fresh"] = usage.get("input_tokens") or 0
    row["write"] = usage.get("cache_creation_input_tokens") or 0
    row["read"] = usage.get("cache_read_input_tokens") or 0
    row["out"] = usage.get("output_tokens") or 0
    row["w1h"] = split.get("ephemeral_1h_input_tokens") or 0
    row["w5m"] = split.get("ephemeral_5m_input_tokens") or 0
    if row["w1h"] + row["w5m"] != row["write"]:  # older transcripts lack the split: count it as 5m
        row["w1h"], row["w5m"] = 0, row["write"]
    row["context"] = row["fresh"] + row["write"] + row["read"]


def email_at(emails, stamp):
    """The account email in force at a time: the last one recorded at or before it."""
    current = emails[0][1] if emails else None
    for seen_at, email in emails:
        if stamp is not None and seen_at > stamp:
            break
        current = email
    return current


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q / 100 * (len(ordered) - 1))))]


def trimmed_mean(values, share=0.1):
    if not values:
        return None
    ordered = sorted(values)
    cut = int(len(ordered) * share)
    kept = ordered[cut:len(ordered) - cut] or ordered
    return sum(kept) / len(kept)


def most_common(values):
    present = [v for v in values if v]
    return max(set(present), key=present.count) if present else None

#!/usr/bin/env python3
# PreToolUse, PostToolUse and PostToolUseFailure on SendMessage: one event, one recipient (docs/PROTOCOL.md),
# plus message_rules.py's body rules. Fails open on every error: only exit 2 blocks, so a guard bug never stops a message.
import fcntl
import json
import math
import os
import re
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

from message_rules import content_problem
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

PASS = 0
BLOCK = 2
LINE_ONE = re.compile(r"([A-Z]+(?:-[A-Z]+)*) +([a-z]+-[0-9a-z]+(?:\.[0-9a-z]+)*)(?: +(v[0-9]+))?")
NAME_FIELD_BY_RECORD_TYPE = {"agent-name": "agentName", "custom-title": "customTitle"}
PENDING, SENT, FAILED = "pending", "sent", "failed"
RECORD_FIELDS = ("state", "sender", "key", "to", "tool_use_id", "time")
# A denied prompt can end a send with neither Post event, so a pending send must stop blocking on its own.
PENDING_WINDOW = timedelta(seconds=120)


def sent_log_path() -> Path:
    # Outside the session on purpose: the log must outlive a restarted session and its transcript.
    return Path(suite_config.board_file("AGENT_SENT_LOG", "sent.jsonl"))


def event_key(message) -> str | None:
    if not isinstance(message, str):
        return None
    match = LINE_ONE.fullmatch(message.partition("\n")[0].strip())
    return " ".join(part for part in match.groups() if part) if match else None


def parsed(line: str):
    try:
        return json.loads(line)
    except ValueError:
        return None


def session_name(transcript_lines) -> str | None:
    # The name, never the session id: past ~120k tokens a session restarts in a new transcript under the same name.
    name = None
    for line in transcript_lines:
        # Transcripts grow to megabytes and the hook runs on every send, so only lines that can hold a name are parsed.
        if not any(record_type in line for record_type in NAME_FIELD_BY_RECORD_TYPE):
            continue
        record = parsed(line)
        if isinstance(record, dict) and record.get("type") in NAME_FIELD_BY_RECORD_TYPE:
            name = record.get(NAME_FIELD_BY_RECORD_TYPE[record["type"]])
    return name if isinstance(name, str) and name.strip() else None


def sender_of(transcript_path) -> str | None:
    if not isinstance(transcript_path, str):
        return None
    try:
        with open(transcript_path, encoding="utf-8") as transcript:
            return session_name(transcript)
    except (OSError, ValueError):
        return None


def addressed_send(hook: dict) -> dict | None:
    tool_input = hook.get("tool_input") or {}
    key = event_key(tool_input.get("message"))
    recipient = tool_input.get("to")
    tool_use_id = hook.get("tool_use_id")
    if not key or not all(isinstance(value, str) and value.strip() for value in (recipient, tool_use_id)):
        return None
    sender = sender_of(hook.get("transcript_path"))
    return {"sender": sender, "key": key, "to": recipient, "tool_use_id": tool_use_id} if sender else None


def records_of_event(log, send: dict) -> list[dict]:
    # The log only grows and every send reads it, so only lines naming this event's key are parsed.
    quoted_key = json.dumps(send["key"])
    records = (parsed(line) for line in log if quoted_key in line)
    return [
        record for record in records
        if isinstance(record, dict) and record.get("state") in (PENDING, SENT, FAILED)
        and all(isinstance(record.get(field), str) for field in RECORD_FIELDS)
        and record["sender"] == send["sender"] and record["key"] == send["key"]
    ]


def age_of(record: dict, now: datetime) -> timedelta | None:
    try:
        return now - datetime.fromisoformat(record["time"])
    except (ValueError, TypeError):
        return None


def blocking_reason(records: list[dict], send: dict, now: datetime) -> str | None:
    sender, key = send["sender"], send["key"]
    others = [record for record in records if record["to"] != send["to"]]
    delivered_to = next((record["to"] for record in others if record["state"] == SENT), None)
    if delivered_to:
        return (
            f"send_guard: {sender!r} already sent {key!r} to {delivered_to!r}; one event goes to one recipient "
            f"(docs/PROTOCOL.md). Resend it to {delivered_to!r}, or give a new event a new version."
        )
    failed_ids = {record["tool_use_id"] for record in others if record["state"] == FAILED}
    pending_ages = [
        (record["to"], age) for record in others
        if record["state"] == PENDING and record["tool_use_id"] not in failed_ids
        and (age := age_of(record, now)) is not None and timedelta(0) <= age < PENDING_WINDOW
    ]
    if not pending_ages:
        return None
    pending_to, youngest = min(pending_ages, key=lambda pending: pending[1])
    wait = math.ceil((PENDING_WINDOW - youngest).total_seconds())
    return (
        f"send_guard: {sender!r} is sending {key!r} to {pending_to!r} with no result yet; one event goes to one "
        f"recipient (docs/PROTOCOL.md). A send with no result blocks other recipients for at most "
        f"{PENDING_WINDOW.seconds} s: resend in {wait} s, or send it to {pending_to!r} now."
    )


def append_record(state: str, log, send: dict, now: datetime) -> None:
    log.write(json.dumps({"state": state, **send, "time": now.isoformat(timespec="seconds")}) + "\n")


def reserve(log, send: dict, now: datetime) -> str | None:
    reason = blocking_reason(records_of_event(log, send), send, now)
    if not reason:
        append_record(PENDING, log, send, now)
    return reason


HANDLER_BY_EVENT = {"PreToolUse": reserve, "PostToolUse": partial(append_record, SENT), "PostToolUseFailure": partial(append_record, FAILED)}


@contextmanager
def locked(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a+", encoding="utf-8") as log:
        # Parallel sends run their hooks at once: check and reserve must be one step, or both read an empty log and pass.
        fcntl.flock(log, fcntl.LOCK_EX)
        log.seek(0)
        yield log


def verdict(hook: dict, log_path: Path, now: datetime) -> str | None:
    handler = HANDLER_BY_EVENT.get(hook.get("hook_event_name"))
    if handler is reserve and hook.get("tool_name") == "SendMessage":
        problem = content_problem((hook.get("tool_input") or {}).get("message"), hook.get("transcript_path"))
        if problem:
            return problem
    send = addressed_send(hook) if handler and hook.get("tool_name") == "SendMessage" else None
    if not send:
        return None
    with locked(log_path) as log:
        return handler(log, send, now)


def main() -> int:
    try:
        reason = verdict(json.load(sys.stdin), sent_log_path(), datetime.now(UTC))
    except Exception:  # noqa: BLE001
        # Any error lets the message through, so the only way this hook blocks is its own verdict below.
        return PASS
    if not reason:
        return PASS
    print(reason, file=sys.stderr)
    return BLOCK


if __name__ == "__main__":
    sys.exit(main())

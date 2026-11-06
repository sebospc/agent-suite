import json
import os
import re
from collections import deque
from typing import Dict, List, Tuple

from cockpit.transcripts.own_words import excerpt, own_words
from cockpit.transcripts.prompt import prompt_of, review_request_of, text_of
from cockpit.times import parse_time

BEAD_ID = re.compile(r"\b(?:pg|mb)-[a-z0-9]{3,5}(?:\.\d+)*\b")
# An id needs a digit: decade, facade and defaced are words, not ids.
ASK_ID = re.compile(r"\bask\s+((?=[0-9a-f]*\d)[0-9a-f]{6})\b", re.I)
# Not "sha": "Patch sha c26c4e65" and "(sha 3d8db354)" are patch sha256 receipts, not commits.
COMMIT = re.compile(r"\b(?:commit|landed|pushed)\s+((?=[0-9a-f]*\d)[0-9a-f]{7,40})\b", re.I)
# A reply that says it saved or recorded something should name where (the owner: no id, it does not exist).
# Saving a pid or a backup records no decision, so it needs no id (brain's F19: "saved pid only").
# ponytail: a word list; grow it when another false positive shows under Said vs saved.
SAVED = re.compile(r"\b(?:saved|recorded|guardad[oa]s?|registrad[oa]s?)\b(?!\s+(?:(?:the|its|a|an)\s+)?(?:pid|backup|copy|screenshot)s?\b)", re.I)
# "6152 saved apps", "the real recorded mockup", "a saved-app test": saved as an adjective describes data, it claims no
# save (10 of the 25 no-id rows on 2026-11-05).
ATTRIBUTIVE = re.compile(r"\b(?:a|an|the|its|each|every|\d[\d,]*)\s+(?:[\w-]+\s+)?(?:saved|recorded)[\s-]+"
                         r"(?!(?:by|in|to|as|at|on|for|with|without|from|through|under|into)\b)[a-z]", re.I)
# Where a reply says it saved something decides how far it can be trusted (design chat N20).
PLACES = (("scratchpad", re.compile(r"(?:/private)?/tmp/|scratchpad")), ("agent memory", re.compile(r"/memory/|project_\w+\.md|MEMORY\.md")),
          ("a file", re.compile(r"[\w.-]+/[\w./-]+\.\w+")))
FILE_NAME = r"\b[\w-]+\.(?:json|jsonl|md|py|sh|js|mjs|ts|swift|kt|yml|yaml|txt|toml)\b"  # a bare file name says where it was saved
# The token tools (ask 8ccee2), known by the hook command Claude Code records for each run; caveman and ponytail record
# their loading line ("Loading caveman mode...") as the command.
TOKEN_TOOLS = (("rtk", "rtk hook"), ("context-mode", "context-mode"), ("caveman", "caveman"), ("ponytail", "ponytail"))
# A SessionStart hook that switches a writing mode on says so in its first line ("CAVEMAN MODE ACTIVE — level: full").
MODE_LINE = re.compile(r"^([A-Z][A-Z-]+) MODE ACTIVE", re.M)
# A blocking error is a hook saying no on purpose; these two are a hook that crashed or timed out.
HOOK_FAILURES = ("hook_non_blocking_error", "hook_cancelled")
# Jev's session verdict reads the last few turns, never the whole transcript (design Q4: costly and noisy).
LAST_TURN_LINES, TURN_CHARS = 6, 500
ANY_ID = re.compile(r"\b(?:pg|mb)-[a-z0-9]{3,5}|\b(?=[0-9a-f]*\d)[0-9a-f]{6,40}\b|[\w.-]+/[\w./-]+|" + FILE_NAME)


class TranscriptFile:
    """One transcript read incrementally by byte offset. Requests are deduplicated by message.id: one
    response is written as up to 4 lines repeating its usage, the last carrying the final output count."""

    def __init__(self, path: str):
        self.path = path
        self.offset = 0
        self.rows: Dict[str, dict] = {}
        self.boundaries: List[dict] = []
        self.titles: List[str] = []
        self.mentions: List[Tuple[float, str]] = []
        self.ids: List[Tuple[float, str, str]] = []  # (time, "ask" or "commit", id) named in replies
        self.evidence: List[Tuple[float, str, str, str]] = []  # (time, bead|ask|commit|saved, id, the reply line) behind the lists below
        self.saved_without_id: List[float] = []
        self.saved_places: List[Tuple[float, str]] = []
        self.prompts: List[dict] = []  # main-thread user lines that start a turn, oldest first (prompt_of)
        self.review_requests: List[dict] = []  # GO-REQs this session sent: {t, row, bead, sha256}; row keys self.rows
        self.seen_sends: set = set()
        self.tool_runs: Dict[str, float] = {}  # token tool -> when its hook last ran fine
        self.tool_failures: List[Tuple[float, str, str]] = []  # (time, token tool, what its hook said)
        self.start_modes: List[Tuple[float, str]] = []  # (time, mode) each SessionStart hook switched on
        self.hook_outputs: Dict[str, Tuple[float, int]] = {}  # hook command -> (time, characters) of its last output
        self.last_start = 0.0  # its last SessionStart hook: a start, resume, clear or compaction
        self.cwd = ""  # the folder the session runs in: which CLAUDE.md files it loads
        self.last_turns: deque = deque(maxlen=LAST_TURN_LINES)  # (time, "asked" or "replied", text cut to TURN_CHARS)

    def update(self) -> None:
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return
        if size < self.offset:  # rewritten from the start
            self.__init__(self.path)
        if size == self.offset:
            return
        with open(self.path, "rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read(size - self.offset)
        complete = chunk.rfind(b"\n") + 1  # a line still being written is read next time
        self.offset += complete
        for line in chunk[:complete].splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                self.take(entry)

    def take(self, entry: dict) -> None:
        kind = entry.get("type")
        stamp = parse_time(entry.get("timestamp"))
        if entry.get("cwd") and not entry.get("isSidechain"):
            self.cwd = entry["cwd"]
        if kind == "system" and (entry.get("subtype") == "compact_boundary" or "compactMetadata" in entry):
            meta = entry.get("compactMetadata") or {}
            self.boundaries.append({"at": stamp or 0.0, "trigger": meta.get("trigger") or "",
                                    "pre": meta.get("preTokens"), "post": meta.get("postTokens") or None})
        elif kind == "custom-title" and entry.get("customTitle"):
            self.titles.append(entry["customTitle"])
        elif kind == "ai-title" and entry.get("aiTitle") and not self.titles:
            self.titles.append(entry["aiTitle"])  # DATA_SOURCES.md: custom-title wins; an ai-title only stands in for it
        elif kind == "assistant":
            self.take_assistant(entry, stamp)
        elif kind == "attachment":
            self.take_hook(entry.get("attachment") or {}, stamp)
        elif kind == "user" and not entry.get("isSidechain") and not entry.get("isMeta"):
            prompt = prompt_of(entry.get("message") or {}, stamp)
            if prompt:
                self.prompts.append(prompt)
                if prompt["origin"] in ("person", "peer"):
                    self.last_turns.append((stamp or 0.0, "asked", text_of(entry.get("message") or {})[:TURN_CHARS]))

    def take_assistant(self, entry: dict, stamp) -> None:
        message = entry.get("message") or {}
        usage = message.get("usage") or {}
        if not usage or message.get("model") in (None, "<synthetic>"):
            return
        key = message.get("id") or entry.get("requestId") or f"line{len(self.rows)}"
        row = self.rows.get(key)
        if row is None:
            row = self.rows[key] = {"model": message.get("model"), "effort": entry.get("effort") or "",
                                    "sidechain": bool(entry.get("isSidechain")), "t_first": stamp, "t_last": stamp,
                                    "out": -1, "tools": []}
        if stamp is not None:
            row["t_first"] = stamp if row["t_first"] is None else min(row["t_first"], stamp)
            row["t_last"] = stamp if row["t_last"] is None else max(row["t_last"], stamp)
        if (usage.get("output_tokens") or 0) >= row["out"]:
            set_usage(row, usage)
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                given = block.get("input") or {}
                row["tools"].append((block.get("name"), given.get("file_path") or given.get("path") or given.get("pattern")
                                     or given.get("command") or given.get("skill")))
                if not row["sidechain"]:
                    self.take_review_request(block, key, stamp)
            elif block.get("type") == "text" and not row["sidechain"]:
                text = block.get("text") or ""
                if text.strip():
                    self.last_turns.append((stamp or 0.0, "replied", text[:TURN_CHARS]))
                mine = own_words(text)
                for kind, pattern in (("bead", BEAD_ID), ("ask", ASK_ID), ("commit", COMMIT)):
                    for found in pattern.finditer(mine):
                        ident = (found.group(1) if pattern.groups else found.group()).lower()
                        self.evidence.append((stamp or 0.0, kind, ident, excerpt(text, found.start())))
                        (self.mentions.append((stamp or 0.0, found.group())) if kind == "bead" else self.ids.append((stamp or 0.0, kind, ident)))
                saying = next((m for m in SAVED.finditer(mine)
                               if not any(a.start() <= m.start() < a.end() for a in ATTRIBUTIVE.finditer(mine))), None)
                if saying:
                    if not ANY_ID.search(text):
                        self.saved_without_id.append(stamp or 0.0)
                        self.evidence.append((stamp or 0.0, "saved", "", excerpt(text, saying.start())))
                    place = next((name for name, pattern in PLACES if pattern.search(text)), "")
                    if place:
                        self.saved_places.append((stamp or 0.0, place))

    def take_hook(self, hook: dict, stamp) -> None:
        if hook.get("hookEvent") == "SessionStart":
            self.last_start = max(self.last_start, stamp or 0.0)
        if hook.get("hookEvent") == "SessionStart" and hook.get("type") == "hook_success":
            said = str(hook.get("stdout") or hook.get("content") or "")
            self.start_modes += [(stamp or 0.0, mode.lower()) for mode in MODE_LINE.findall(said)]
        if hook.get("type") == "hook_success" and hook.get("command"):
            # stdout keeps the whole output; content holds the 2k stub Claude Code puts in its place past 10,000.
            self.hook_outputs[hook["command"]] = (stamp or 0.0, len(str(hook.get("stdout") or hook.get("content") or "")))
        tool = next((name for name, word in TOKEN_TOOLS if word in (hook.get("command") or "")), None)
        if tool is None:
            return
        if hook.get("type") == "hook_success":
            self.tool_runs[tool] = stamp or 0.0
        elif hook.get("type") in HOOK_FAILURES:
            said = hook.get("stderr") or ("timed out" if hook.get("timedOut") else hook["type"])
            self.tool_failures.append((stamp or 0.0, tool, said[:200]))

    def take_review_request(self, block: dict, key: str, stamp) -> None:
        """The send tool's input field names are not documented, so every text in the input is tried; a block repeated
        across the lines of one response is taken once (by the tool call id)."""
        call = block.get("id")
        if call and call in self.seen_sends:
            return
        for value in (block.get("input") or {}).values():
            found = review_request_of(value) if isinstance(value, str) else None
            if found:
                self.seen_sends.add(call)
                self.review_requests.append(dict(found, t=stamp or 0.0, row=key))
                return

    def requests(self) -> List[dict]:
        return sorted(self.rows.values(), key=lambda r: r["t_first"] or 0.0)


def set_usage(row: dict, usage: dict) -> None:
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

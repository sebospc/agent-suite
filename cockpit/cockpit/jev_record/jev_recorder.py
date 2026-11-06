import threading
from typing import Callable, Dict, List, Optional

from cockpit.action_log.action_log import ActionLog
from cockpit.milestone.tree import BeadTree
from cockpit.source_unavailable import SourceUnavailable
from cockpit.tokens.landed_beads import bead_window, spent_on
from cockpit.transcripts.history import History



class JevRecorder:
    """The Jev record (the owner, 2026-10-16): each bead's suggestion beside the model and effort that ran, then its
    outcome when it closes (tokens and turns while in progress, HOLDs). Without it, shadow mode decides nothing."""

    def __init__(self, record: ActionLog, log: Callable[[str], None]):
        self.record = record
        self.log = log
        self.lock = threading.Lock()
        self.loaded = False
        self.seen: set = set()
        self.suggested: Dict[str, dict] = {}   # bead -> its first suggestion record
        self.outcomes: Dict[str, dict] = {}
        self.error = ""

    def load(self) -> None:
        if self.loaded:
            return
        for entry in self.record.since(0):
            if entry.get("event") == "suggested":
                self.seen.add(key_of(entry))
                self.suggested.setdefault(entry["bead"], entry)
            elif entry.get("event") == "outcome":
                self.outcomes[entry["bead"]] = entry
        self.loaded = True

    def step(self, rows: List[dict], tree: Optional[BeadTree], history: Optional[History], history_start: float, now: float) -> int:
        try:
            with self.lock:
                self.load()
                written = self.note_suggestions(rows, now) + (self.note_outcomes(tree, history, history_start, now) if tree and history else 0)
            self.error = ""
            return written
        except SourceUnavailable as error:
            self.error = str(error)
            self.log(f"jev record: {error}")
            return 0

    def note_suggestions(self, rows: List[dict], now: float) -> int:
        written = 0
        for row in rows:
            s = row.get("suggested")
            if not s or not s.get("bead"):  # outcomes are per bead; a session with none has nothing to score yet
                continue
            entry = {"t": now, "event": "suggested", "bead": s["bead"], "session": row["name"], "jev_model": s["model"],
                     "jev_effort": s["effort"], "ran_model": row["model"], "ran_effort": row["effort"], "agrees": s["agrees"],
                     "by": s.get("by", ""), "start": s.get("start", ""), "window": s.get("window", ""),
                     "why": s.get("why", ""), "bead_why": s.get("bead_why", ""), "related": s.get("related"), "long": s.get("long")}
            if key_of(entry) in self.seen:
                continue
            self.record.append(entry)
            self.seen.add(key_of(entry))
            self.suggested.setdefault(s["bead"], entry)
            written += 1
        return written

    def note_outcomes(self, tree: BeadTree, history: History, history_start: float, now: float) -> int:
        written = 0
        for bead_id in [b for b in self.suggested if b not in self.outcomes]:
            bead = tree.by_id.get(bead_id)
            if not bead or bead.status != "closed":
                continue
            spent = spent_on(bead, history.requests) or {"tokens": None, "turns": None}
            window = bead_window(bead)
            entry = {"t": now, "event": "outcome", "bead": bead_id, "session": bead.assignee, "closed_at": bead.closed_at,
                     "tokens": spent["tokens"], "turns": spent["turns"],
                     "holds": sum(1 for m in history.messages if m.type == "HOLD" and m.bead == bead_id),
                     # Transcripts are read back 14 days: a bead in progress longer has part of its spend left out.
                     "partial": bool(window and window[0] < history_start)}
            self.record.append(entry)
            self.outcomes[bead_id] = entry
            written += 1
        return written

    def summary(self, now: float) -> dict:
        with self.lock:
            firsts = [e["t"] for e in self.suggested.values()]
            classes: Dict[str, dict] = {}
            for bead_id, s in self.suggested.items():
                c = classes.setdefault(f"{s['jev_model']} {s['jev_effort']}", {"name": f"{s['jev_model']}, {s['jev_effort']}",
                                                                                "beads": 0, "agreed": 0, "closed": 0, "tokens": 0, "holds": 0})
                c["beads"] += 1
                c["agreed"] += bool(s.get("agrees"))
                out = self.outcomes.get(bead_id)
                if out:
                    c["closed"] += 1
                    c["tokens"] += out.get("tokens") or 0
                    c["holds"] += out.get("holds") or 0
            return {"beads": len(self.suggested), "closed": len(self.outcomes), "error": self.error,
                    "classes": [dict(c, per_bead=round(c["tokens"] / c["closed"]) if c["closed"] else None,
                                     holds_per_bead=round(c["holds"] / c["closed"], 1) if c["closed"] else None)
                                for c in sorted(classes.values(), key=lambda c: -c["beads"])]}


def key_of(entry: dict) -> tuple:
    """A bead is recorded again only when the suggestion or what runs changes."""
    return entry["bead"], entry["jev_model"], entry["jev_effort"], entry["ran_model"], entry["ran_effort"]

from typing import Dict, Optional

from cockpit.action_log.action_log import ActionLog
from cockpit.milestone.tree import BeadTree
from cockpit.source_unavailable import SourceUnavailable

WINDOW_S = 14 * 86400


class BeadWatch:
    """Writes a `bead_reopened` record when a bead the last read saw closed is open again: rework the board keeps no
    count of (design pg-45v5 measure 3). Seen from the cockpit's first read on."""

    def __init__(self, action_log: ActionLog, now: float):
        self.action_log = action_log
        self.status: Dict[str, str] = {}
        self.reopened: Dict[str, float] = {}
        try:
            self.reopened = {r["bead"]: r["t"] for r in action_log.since(now - WINDOW_S) if r.get("event") == "bead_reopened"}
        except SourceUnavailable:
            pass

    def step(self, tree: Optional[BeadTree], now: float) -> None:
        if tree is None:
            return
        for bead in tree.by_id.values():
            if self.status.get(bead.id) == "closed" and bead.status != "closed":
                self.reopened[bead.id] = now
                try:
                    self.action_log.append({"t": now, "event": "bead_reopened", "origin": "board", "bead": bead.id, "status": bead.status})
                except SourceUnavailable:
                    pass
            self.status[bead.id] = bead.status

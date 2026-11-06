import threading
from typing import List, Optional

from cockpit.display_time import day_time
from cockpit.prices.price_page import PricePage
from cockpit.compaction.price_table import PriceTable
from cockpit.source_unavailable import SourceUnavailable

DAY = 86400
RETRY_S = 3600  # a failed read is tried again in an hour, not a day, so one network blip does not hide a change
KEYS = ("input", "write_5m", "write_1h", "cache_read", "output", "step_factor")


def differences(table: PriceTable, page: dict) -> List[str]:
    found = []
    for model, entry in sorted(table.models.items()):
        listed = page.get(model)
        if listed is None:
            found.append(f"{model} is not on the page")
            continue
        for key in KEYS:
            mine, theirs = entry.get(key), listed.get(key)
            if (mine or theirs) and (mine is None or theirs is None or abs(mine - theirs) > 1e-9):
                found.append(f"{model} {key}: {mine} in config/prices.json, {theirs} on the page")
    return found


class PriceCheck:
    """Once a day, compares config/prices.json with Anthropic's prices page (the owner, 2026-10-16: "deberiamos tener
    un cronjob revisando los prices"): the sweet spot minimises dollars per turn with these prices."""

    def __init__(self, page: PricePage, table: PriceTable, source: str):
        self.page = page
        self.table = table
        self.source = source
        self.checked_at: Optional[float] = None
        self.tried_at: Optional[float] = None
        self.found: List[str] = []
        self.error = ""
        self.lock = threading.Lock()

    def due(self, now: float) -> bool:
        if self.tried_at is None:
            return True
        return now - self.tried_at >= (RETRY_S if self.error else DAY)

    def step(self, now: float) -> bool:
        if not self.due(now):
            return False
        try:
            listed = self.page.read()
            found, error, checked = differences(self.table, listed), "", now
        except SourceUnavailable as failure:
            found, error, checked = self.found, str(failure), self.checked_at
        with self.lock:
            self.tried_at, self.checked_at, self.found, self.error = now, checked, found, error
        return True

    def status(self) -> dict:
        with self.lock:
            return {"checked": day_time(self.checked_at), "checked_at": self.checked_at, "tried_at": self.tried_at, "differences": list(self.found),
                    "error": self.error, "source": self.source, "as_of": self.table.as_of}

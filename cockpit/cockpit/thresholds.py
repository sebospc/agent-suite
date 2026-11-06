from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class Threshold:
    value: object
    status: str  # provisional | set | fixed | learned
    source: str
    range: Optional[dict] = None  # learned only: min, max and max_weekly_change_pct (design pg-o1sq Q14)

    def note(self) -> str:
        return "" if self.status != "provisional" else " (provisional threshold)"


class Thresholds:
    """The owner's thresholds from config/thresholds.json; core rules read them here, never a literal."""

    def __init__(self, raw: dict):
        self.items = {key: Threshold(entry["value"], entry.get("status", "provisional"), entry.get("source", ""), entry.get("range"))
                      for key, entry in raw.items() if isinstance(entry, dict) and "value" in entry}

    def __getitem__(self, key: str) -> Threshold:
        return self.items[key]

    def value(self, key: str):
        return self.items[key].value

    def learn(self, key: str, value) -> None:
        """A re-fit inside its range (cockpit/refit/refitter.py); every rule reads the new value on its next read."""
        self.items[key] = replace(self.items[key], value=value, status="learned")

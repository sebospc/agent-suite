from abc import ABC, abstractmethod
from typing import Optional


class WakeForecast(ABC):
    """Port: will an idle session be used again soon? Jev answers it (adapter in cockpit/classifier/jev_wake.py)."""

    @abstractmethod
    def forecast(self, row: dict, idle_since: float, now: float) -> Optional[dict]:
        """{"within_hour": p, "never": p} (yes probabilities) for a session idle since `idle_since`, its last real turn;
        None when there is no forecast, which keeps the rules as they were. Raises SourceUnavailable."""

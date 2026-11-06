from typing import Dict, List, Optional

from cockpit.autopilot.wake_forecast import WakeForecast
from cockpit.source_unavailable import SourceUnavailable


class FakeWakeForecast(WakeForecast):
    def __init__(self, answers: Dict[str, dict], fails: bool = False):
        self.answers = answers
        self.fails = fails
        self.asked: List[str] = []

    def forecast(self, row: dict, idle_since: float, now: float) -> Optional[dict]:
        self.asked.append(row["name"])
        if self.fails:
            raise SourceUnavailable("Jev: no answer")
        return self.answers.get(row["name"])

from typing import Optional

from cockpit.autopilot.wake_forecast import WakeForecast


class NoForecast(WakeForecast):
    """No Jev: a probe is never sent on a guess."""

    def forecast(self, row: dict, idle_since: float, now: float) -> Optional[dict]:
        return None

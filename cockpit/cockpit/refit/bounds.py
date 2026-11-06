from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Range:
    """What a learned number may do on its own (design pg-o1sq Q14; brain: set before a number is marked learned)."""
    low: float
    high: float
    weekly_change_pct: float

    @staticmethod
    def of(raw: Optional[dict]) -> Optional["Range"]:
        return Range(raw["min"], raw["max"], raw["max_weekly_change_pct"]) if raw else None


def bounded(fitted: float, week_start: float, rng: Range) -> Tuple[Optional[float], str]:
    """(the value to use, "") inside the range, moved at most its weekly change from where the week started; or
    (None, why) when the fit is outside the range: that is a proposal for the owner, and nothing changes."""
    if not rng.low <= fitted <= rng.high:
        return None, f"the fit {fitted:g} is outside its range {rng.low:g} to {rng.high:g}"
    step = abs(week_start) * rng.weekly_change_pct / 100
    return round(min(max(fitted, week_start - step), week_start + step), 2), ""

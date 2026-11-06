from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Account:
    number: str
    five_hour_pct: Optional[float]
    five_hour_resets: Optional[float]
    seven_day_pct: Optional[float]
    seven_day_resets: Optional[float]
    age_seconds: Optional[float]
    status: str
    usage_status: str = field(default="")
    disabled: bool = field(default=False)
    active: bool = field(default=False)  # logged in on ~/.claude itself, not only in its cswap profile

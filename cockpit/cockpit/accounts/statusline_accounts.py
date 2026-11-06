import json
import os
import time
from typing import Callable, List

from cockpit.accounts.account import Account
from cockpit.accounts.accounts import Accounts
from cockpit.source_unavailable import SourceUnavailable


# The name the live sessions give ~/.claude's login (cswap_herdr_sessions), so every team session maps to it.
ONE_LOGIN = "default"


class StatuslineAccounts(Accounts):
    """The one login's plan limits, as Claude Code last handed them to the status line (~/.claude/statusline.sh saves them).

    Replaces cswap (removed 2026-11-05): one account on ~/.claude, so no token is read and no undocumented endpoint is called."""

    def __init__(self, path: str, now: Callable[[], float] = time.time):
        self.path = os.path.expanduser(path)
        self.now = now

    def list(self) -> List[Account]:
        try:
            with open(self.path, encoding="utf-8") as saved:
                raw = json.load(saved)
        except (OSError, ValueError) as error:
            raise SourceUnavailable(f"{self.path}: {error}")
        limits = raw.get("rate_limits") or {}
        five, seven = limits.get("five_hour") or {}, limits.get("seven_day") or {}
        at = raw.get("at")
        return [Account(number=ONE_LOGIN, five_hour_pct=number(five.get("used_percentage")), five_hour_resets=number(five.get("resets_at")),
                        seven_day_pct=number(seven.get("used_percentage")), seven_day_resets=number(seven.get("resets_at")),
                        age_seconds=self.now() - at if isinstance(at, (int, float)) else None, status="", active=True)]


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

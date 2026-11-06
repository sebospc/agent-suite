import time
from typing import List, Optional

from cockpit.accounts.account import Account
from cockpit.display_time import age, clock_time, day_time, when
from cockpit.thresholds import Thresholds


def reset_time(epoch: Optional[float], now: float) -> str:
    """The date with its day number (the owner, 2026-10-16: a weekday name does not say which date); the clock alone
    only when the reset is today."""
    if not epoch:
        return ""
    same_day = time.localtime(epoch)[:3] == time.localtime(now)[:3]
    return clock_time(epoch) if same_day else day_time(epoch)


def accounts_section(accounts: List[Account], rows: List[dict], thresholds: Thresholds, now: float) -> List[dict]:
    mark = thresholds.value("account_5h_mark_pct")
    shown = []
    for account in sorted(accounts, key=lambda a: -(a.five_hour_pct or 0)):
        on_it = [r["name"] for r in rows if r["account"] == account.number]
        shown.append({
            "number": account.number, "sessions": ", ".join(on_it) or "no team session",
            "five_hour": account.five_hour_pct, "five_hour_resets": reset_time(account.five_hour_resets, now),
            "seven_day": account.seven_day_pct, "seven_day_resets": reset_time(account.seven_day_resets, now),
            "over_mark": (account.five_hour_pct or 0) >= mark, "mark": mark,
            "age": age(account.age_seconds) if account.age_seconds is not None else "", "status": account.status,
        })
    return shown


def balancer_rows(decisions: List[dict], now: float) -> List[dict]:
    rows = []
    for decision in sorted(decisions, key=lambda d: -d["t"]):  # all of the last 24 h: they live in the closed log
        session = decision.get("session") or decision.get("name") or "a session"
        chosen = decision.get("chosen") or decision.get("account")
        reason = decision.get("reason") or "no reason recorded"
        rows.append({"t": when(decision["t"], now), "at": decision["t"], "text": f"{session}: account {chosen}. {reason}"})
    return rows

import time
from typing import Optional


def clock_time(epoch: Optional[float]) -> str:
    """Local time of the Mac the cockpit runs on, which is the owner's."""
    return "" if not epoch else time.strftime("%H:%M", time.localtime(epoch))


def day_time(epoch: Optional[float]) -> str:
    return "" if not epoch else time.strftime("%b %-d, %H:%M", time.localtime(epoch))


def day(epoch: Optional[float]) -> str:
    return "" if not epoch else time.strftime("%b %-d", time.localtime(epoch))


def age(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    if seconds < 90:
        return f"{max(0, int(seconds))} s"
    if seconds < 5400:
        return f"{round(seconds / 60)} m"
    if seconds < 2 * 86400:
        return f"{round(seconds / 3600)} h"
    return f"{round(seconds / 86400)} d"


def when(epoch: Optional[float], now: float) -> str:
    """The clock for today, the date and clock for any other day, so yesterday's 23:10 never reads as today's."""
    if not epoch:
        return ""
    return clock_time(epoch) if time.localtime(epoch)[:3] == time.localtime(now)[:3] else day_time(epoch)


def clock_seconds(epoch: Optional[float]) -> str:
    return "" if not epoch else time.strftime("%H:%M:%S", time.localtime(epoch))

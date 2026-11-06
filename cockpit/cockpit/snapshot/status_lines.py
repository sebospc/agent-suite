from typing import List, Optional, Tuple

from cockpit.accounts.account import Account
from cockpit.accounts.login import logins_by_use, needs_login, why_login
from cockpit.git.gate_state import GateState


def millions(tokens: int) -> str:
    return f"{tokens / 1e6:.1f}M"


def handled_lines(accounts: List[dict], raw: List[Account], rows: List[dict], next_pick: str, autopilot_on: bool = False) -> List[str]:
    """Abnormal, but something else deals with it: the balancer, and the autopilot when it is on."""
    live = [r["account"] for r in rows if r["state"] != "off" and r["account"]]
    _, unused = logins_by_use(raw, live, next_pick)
    logged_out = {a.number for a in raw if needs_login(a)}  # their 5h value is an old one, and the login is the real issue
    return ([f"account {a['number']} at {a['five_hour']:.0f}% of 5h; the balancer keeps new and cold sessions off it"
             for a in accounts if a["over_mark"] and a["five_hour"] is not None and a["number"] not in logged_out]
            + [f"account {a.number} needs a login ({why_login(a)}), but nothing runs on it"
               for a in unused]
            + ([f"{r['name']} is over its sweet spot while busy; the autopilot compacts it once it is idle with its notes saved"
                for r in rows if r["over"] and r["state"] == "busy"] if autopilot_on else []))


def with_cache(no_cache: int, cached: int) -> str:
    """Cache reads are most of a day's tokens and cost a tenth of an input token (brain's pg-tg71), so they come second."""
    return f"{millions(no_cache + cached)} with cache"


def clear_lines(gate: Optional[GateState], tokens: Optional[Tuple[int, int, int]], process: Optional[dict] = None) -> List[str]:
    lines = []
    if process and not process["today_duplicates"]:
        lines.append("no duplicate message today")
    if process and not process["this_week"]["outside_format"]:
        lines.append("no message outside the WORKFLOW format this week")
    if gate and gate.green and not gate.unpushed:
        lines.append(f"main is green (gate on {gate.commit}), nothing waits to be pushed")
    if tokens:
        yesterday, today, cached = tokens
        counted = f"{millions(today)} tokens today without cache ({with_cache(today, cached)})"
        if yesterday:
            change = round((today / yesterday - 1) * 100)
            direction = "over" if change > 0 else "under"
            lines.append(f"{counted}, {abs(change)}% {direction} yesterday at this time")
        else:
            lines.append(counted)
    return lines

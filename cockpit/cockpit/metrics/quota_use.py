from typing import Callable, Dict, List, Optional

from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.source_unavailable import SourceUnavailable

AREA, DAY = "quota_use", 86400
READ_EVERY_S = 600  # the history reads the whole metrics file; quota moves slowly
RULE = "UNKNOWN until an account has 24 h of 7 d readings in the metrics history and its sessions finished a task"
SOURCE = "cswap list (7 d use per account) as metrics.jsonl kept it each read, transcripts (bd close per session), 24 h"


def points_used(points: List[list]) -> float:
    """7 d percentage points spent: the sum of its rises; a weekly reset drops it, which is not spending."""
    values = [v for _, v in points if isinstance(v, (int, float))]
    return sum(max(0.0, b - a) for a, b in zip(values, values[1:]))


class QuotaUse:
    """Design pg-o1sq Q13, quota per finished task: the 7 d points each account spent in 24 h over the tasks its
    sessions closed (heuristic: a session counts on the account it runs on now). Jev's session verdict reads its
    account's figure."""

    def __init__(self, history: Callable[[str, str, str, float], List[list]]):
        self.history = history
        self.read_at = 0.0
        self.used: Dict[str, float] = {}
        self.per_account: Dict[str, float] = {}
        self.error = ""

    def step(self, snapshot: dict, now: float) -> dict:
        accounts = [a for a in snapshot.get("accounts") or [] if a.get("seven_day") is not None]
        if now - self.read_at >= READ_EVERY_S:
            self.read_at = now
            try:
                found = {a["number"]: self.history(AREA, f"acct-{a['number']}", "seven_day", now - DAY) for a in accounts}
                # Only an account whose history reaches back the whole 24 h has a figure; a new one would read as 0.
                self.used = {n: points_used(p) for n, p in found.items() if p and p[0][0] <= now - DAY}
                self.error = ""
            except SourceUnavailable as error:
                self.error = str(error)
        outcomes = next((l for l in snapshot["health"] if l["id"] == "outcomes"), {}).get("table") or {}
        tasks_of = {r["session"]: r["tasks"] for r in outcomes.get("rows") or []}
        tasks: Dict[str, int] = {}
        for row in snapshot["sessions"]:
            if row.get("account"):
                tasks[row["account"]] = tasks.get(row["account"], 0) + tasks_of.get(row["name"], 0)
        rows = [{"id": f"acct-{a['number']}", "account": a["number"], "seven_day": a["seven_day"],
                 "used": round(self.used[a["number"]], 1) if a["number"] in self.used else None,
                 "tasks": tasks.get(a["number"], 0), "per_task": per_task(self.used.get(a["number"]), tasks.get(a["number"], 0))} for a in accounts]
        self.per_account = {r["account"]: r["per_task"] for r in rows if r["per_task"] is not None}
        counted = [r for r in rows if r["used"] is not None]
        used, done = sum(r["used"] for r in counted), sum(r["tasks"] for r in counted)
        team = per_task(used, done)
        columns = [("account", "Account", "text"), ("seven_day", "7 d now %", "count"), ("used", "Points used, 24 h", "count"),
                   ("tasks", "Tasks, 24 h", "count"), ("per_task", "Points per task", "count")]
        why = (f"{used:g} points of 7 d quota spent over {done} finished task{'' if done == 1 else 's'} in 24 h" if team is not None
               else "No account has 24 h of 7 d readings with a finished task yet") + ". Heuristic: a session counts on the account it runs on now"
        if self.error:
            return light(AREA, "Quota per task", "unknown", "unknown", "", self.error, RULE, SOURCE, table("Quota per finished task", columns, rows))
        return light(AREA, "Quota per task", f"{team:g} points per task" if team is not None else "unknown", "ok" if team is not None else "unknown",
                     "", why + ".", RULE, SOURCE, table("Quota per finished task per account, 24 h", columns, rows))


def per_task(used: Optional[float], tasks: int) -> Optional[float]:
    return round(used / tasks, 2) if used is not None and tasks else None

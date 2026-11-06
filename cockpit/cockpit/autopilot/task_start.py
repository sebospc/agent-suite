from typing import Optional, Set

from cockpit.autopilot.compact_text import compact_text
from cockpit.autopilot.task_folders import folders_of, shares_folder

# Design pg-o1sq Q6: never at a task end; decided once per TASK, just before the cockpit types it.
TASK_START = "Clear, compact or keep when a TASK arrives"


def keep_why(row: dict, s: dict, only_compact: Set[str]) -> str:
    """Why its context is worth keeping for the TASK's bead; empty when a clear is safe. A clear needs Jev's fresh
    start and a bead in other folders than the finished one (the owner, 4f79d1)."""
    if s.get("needs_history"):
        return "needs what it worked out"
    if s.get("related"):
        return "is related to what it worked on last"
    if row["name"] in only_compact:
        return "it had 2 wrong clears in 7 days"
    if not s.get("next_folders"):
        return "names no folder, so it may be related work"
    done = set(s.get("done_folders") or []) | folders_of(row.get("task_files") or [])
    if shares_folder(s["next_folders"], done):
        return f"touches the folders of {s.get('done_bead') or 'its last task'}"
    return ""


def cache_cold(row: dict, idle: float) -> bool:
    """An unknown cache life counts as warm, so a clear is never sent on a guess."""
    return bool(row.get("cache_ttl")) and idle >= row["cache_ttl"]


def task_start(row: dict, task: dict, line: Optional[float], idle: float, only_compact: Set[str]) -> dict:
    """Q8 rows 1 to 4. The fact behind them: after its cache expires, the next turn pays full price for the whole
    context, compacted or not; before expiry a compaction costs a tenth. Returns kind compact, clear or keep."""
    context = row["context"] or 0
    size = f"{round(context / 1000)}k"
    over = line is not None and context >= line
    bead = task.get("bead") or ""
    s = row.get("suggested") or {}
    judged = bool(bead) and s.get("bead") == bead and "needs_history" in s
    if not cache_cold(row, idle):
        if not over:
            return arrival(row, task, 1, "keep", f"{size}, under its line, and its cache is warm")
        # Brain, step 3 review: a summary of work the next bead does not need is worth less than a clear.
        if judged and not s["needs_history"] and not row["holds"] and row.get("kind") != "role" and not keep_why(row, s, only_compact):
            return arrival(row, task, 1, "clear", f"{size} over its line and {bead} starts fresh in other folders, so a clear beats a compaction")
        return arrival(row, task, 1, "compact", f"{size} over its line of {round(line / 1000)}k and its cache is warm, so it compacts at a tenth of the price")
    if over:
        # Brain, pg-o1sq relaunch HOLD finding 3: cold and over its line, it is never kept at that size.
        return cold_over_line(row, task, bead, s, judged, size, only_compact)
    if not judged:
        return arrival(row, task, 2, "keep", f"its cache is cold and Jev has no verdict on {bead or 'a bead in the TASK'} yet, so nothing is dropped")
    if s.get("needs_history"):
        return arrival(row, task, 4, "keep", f"its cache is cold and {bead} needs what it worked out; {size} is small enough to read once")
    if row["holds"] or row.get("kind") == "role":
        # Q8 row 7, and a role's context is its continuity: neither is ever cleared.
        held = "it holds a bead in progress" if row["holds"] else "it is a role session"
        return arrival(row, task, 7, "keep", f"its cache is cold and {held}, so it is never cleared")
    why = keep_why(row, s, only_compact)
    if why:
        return arrival(row, task, 2, "keep", f"its cache is cold and {bead} {why}; the one full read happens anyway, then it is cached")
    return arrival(row, task, 3, "clear", f"its cache is cold and {bead} starts fresh in other folders, so a clear loses nothing")

def cold_over_line(row: dict, task: dict, bead: str, s: dict, judged: bool, size: str, only_compact: Set[str]) -> dict:
    """Compact when its work may matter to the bead, clear when it does not. A held bead or a role is never cleared."""
    if not judged:
        return arrival(row, task, 2, "compact", f"its cache is cold, {size} is over its line and Jev has no verdict on "
                                                f"{bead or 'a bead in the TASK'} yet, so it compacts rather than drop anything")
    if s.get("needs_history"):
        return arrival(row, task, 4, "compact", f"its cache is cold, {bead} needs what it worked out and {size} is over its line")
    if row["holds"] or row.get("kind") == "role":
        held = "it holds a bead in progress" if row["holds"] else "it is a role session"
        return arrival(row, task, 7, "compact", f"its cache is cold, {size} is over its line and {held}, so it compacts, never clears")
    why = keep_why(row, s, only_compact)
    if why:
        return arrival(row, task, 2, "compact", f"its cache is cold, {size} is over its line and {bead} {why}")
    return arrival(row, task, 3, "clear", f"its cache is cold, {size} is over its line and {bead} starts fresh in other folders, so a clear loses nothing")


def arrival(row: dict, task: dict, case: int, kind: str, reason: str) -> dict:
    return {"session": row["name"], "rule": TASK_START, "kind": kind, "text": compact_text(row) if kind == "compact" else "" if kind == "keep" else f"/{kind}", "level": "",
            "task": task["id"], "bead": task.get("bead") or "", "case": case, "reason": f"TASK {task['id']}: {reason}"}

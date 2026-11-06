from typing import List

from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light

# Owner panel 848447 (2026-11-05): "B: File it and brain builds it now". That day 29 GB free, a 35-day fseventsd and a
# 23-day orphan grep were found by hand. Disk keeps its own light; this one is the rest of the Mac.
RULE = "ACT when memory free is under its act floor; WATCH under its watch floor, on a process a session left behind, or a session on an older Claude Code"
SOURCE = "sysctl kern.memorystatus_level and vm.swapusage, ps of the user's processes, the version the claude link points to, the tail of each running session's transcript"


def days_or_hours(seconds: int) -> str:
    return f"{seconds // 86400} d" if seconds >= 86400 else f"{seconds // 3600} h"


def mac_light(read: dict, rows: List[dict], watch_free_pct: float, act_free_pct: float) -> dict:
    free, current, orphans = read["memory_free_pct"], read["claude_version"], read["orphans"]
    running = {r["name"]: read["session_versions"].get(r["session_id"]) for r in rows if r["state"] != "off" and r.get("session_id")}
    behind = sorted(name for name, version in running.items() if current and version and version != current)
    level = "act" if free < act_free_pct else "watch" if free < watch_free_pct or orphans or behind else "ok"
    why = "; ".join(p for p in (
        f"memory {free}% free" + (f", swap {read['swap_used_mb'] / 1024:.1f} GB used" if read.get("swap_used_mb") else ""),
        f"{len(orphans)} process{'es' if len(orphans) != 1 else ''} left behind (kill by pid after a look)" if orphans else "",
        f"{', '.join(behind)} on an older Claude Code than {current} (restart picks it up)" if behind else "") if p) + "."
    table_rows = [{"id": "memory", "what": "Memory", "detail": why.split(";")[0].rstrip("."), "age": ""}]
    table_rows += [{"id": name, "what": name, "detail": f"Claude Code {version or 'unknown'}" + (" (current)" if version == current else ""),
                    "age": ""} for name, version in sorted(running.items())]
    table_rows += [{"id": f"pid-{o['pid']}", "what": f"pid {o['pid']}", "detail": o["args"], "age": days_or_hours(o["age_s"])}
                   for o in orphans]
    value = f"{free}% memory free" + (f", {len(orphans)} left behind" if orphans else "") + (f", {len(behind)} behind" if behind else "")
    return light("mac", "Mac", value, level, "", why, RULE, SOURCE,
                 table("The Mac: memory, Claude Code per running session, processes left behind",
                       [("what", "What", "text"), ("detail", "Detail", "text"), ("age", "Age", "text")], table_rows))

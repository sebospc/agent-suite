from typing import List

from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light

# Owner 2026-11-05: "(the owner\'s words)". The team's memory moved to Engram that day (panel f8ec55).
RULE = "ACT when Engram's doctor reports an issue; WATCH when a running session has not loaded Engram's tools"
SOURCE = "engram doctor --json, the Engram store (read-only), the tail of each running session's transcript"


def engram_light(read: dict, rows: List[dict]) -> dict:
    doctor, memories, sessions = read["doctor"], read["memories"], read["sessions"]
    running = [r for r in rows if r["state"] != "off" and r.get("session_id")]
    found = {r["name"]: sessions.get(r["session_id"], {}) for r in running}
    loaded = [name for name, s in found.items() if s.get("loaded")]
    missing = [name for name in found if name not in loaded]
    level = "act" if doctor["issues"] or doctor["status"] != "ok" else "watch" if missing else "ok"
    why = "; ".join(p for p in (
        f"doctor: {'; '.join(doctor['issues']) or doctor['status']}" if level == "act" else "",
        f"{', '.join(missing)} not on Engram yet (restart, then one turn)" if missing else "",
        f"{memories['total']} memories, {memories['saved_today']} saved by sessions today") if p) + "."
    rows_out = [{"id": name, "session": name, "loaded": "yes" if s.get("loaded") else "no", "searches": s.get("searches", 0),
                 "saves": s.get("saves", 0)} for name, s in sorted(found.items())]
    columns = [("session", "Session", "text"), ("loaded", "Engram loaded", "text"), ("searches", "Searches", "count"),
               ("saves", "Saves", "count")]
    return light("engram", "Engram", f"{len(loaded)}/{len(found)} on, {memories['saved_today']} saved today", level, "", why, RULE,
                 SOURCE, table("Engram per session (last 3 MB of each transcript)", columns, rows_out))

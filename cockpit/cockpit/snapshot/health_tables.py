from typing import List, Optional

from cockpit.git.gate_state import GateState

# Each Team health dropdown is a table (the owner, ask 834b86: "solo datos, dinamicos, especialmente tabla"): one row
# per session, tool or measure, a stable id per row, and a one-line caption. Every cell is recorded in metrics.jsonl,
# so units are explicit and the page formats them; a row's id plus a column's key names one measure's history.
# Units: text, flag, tokens, usd, pct, count, gb.
GB = 1024 ** 3


def table(caption: str, columns: List[tuple], rows: List[dict], totals: Optional[List[tuple]] = None) -> dict:
    """columns: (key, label, unit); totals: (key, label, unit, value), the area's own figures beside its rows."""
    return {"caption": caption, "columns": [{"key": k, "label": label, "unit": unit} for k, label, unit in columns],
            "rows": rows, "totals": [{"key": k, "label": label, "unit": unit, "value": v} for k, label, unit, v in totals or []]}


def tokens_table(section: dict) -> dict:
    rows = [{"id": s["name"], "session": s["name"], "account": s.get("account", ""), "model": s.get("model", ""),
             "input": s.get("input"), "output": s.get("output"), "cache_read": s.get("cache_read"), "cache_write": s.get("cache_write"),
             "cache_hit": s.get("cache_hit"), "context": s.get("context"), "cost": s.get("cost"), "idle_cost": s.get("idle_cost"), "per_task": s.get("per_task"), "tokens": s["tokens"], "with_cache": s.get("with_cache"),
             "last_hour": s.get("last_hour"), "share": s["share"], "above_spot": s["above_spot"], "start_load": s["start_load"]} for s in section.get("sessions", [])]
    return table("24 h per session, without cache (input + output); cost at list price, cache writes at the session's TTL tier (~); idle cost: the rewrites and idle compactions of gaps over the cache life, at the same card (~); cache hit: cache reads over input, cache writes and reads",
                 [("session", "Session", "text"), ("account", "Acct", "text"), ("model", "Model", "text"), ("input", "Input", "tokens"),
                  ("output", "Output", "tokens"), ("cache_read", "Cache read", "tokens"), ("cache_write", "Cache write", "tokens"),
                  ("cache_hit", "Cache hit", "pct"), ("context", "Context", "tokens"), ("cost", "Cost", "usd"), ("idle_cost", "Idle cost ~", "usd"), ("per_task", "Per task", "tokens"),
                  ("tokens", "No cache", "tokens"), ("with_cache", "With cache", "tokens"), ("last_hour", "Last hour", "tokens"), ("share", "Share", "pct"), ("above_spot", "Above spot ~", "pct"),
                  ("start_load", "Start ~", "tokens")], rows,
                 [("total_24h", "24 h", "tokens", section.get("total_24h")), ("with_cache_24h", "24 h with cache", "tokens", section.get("with_cache_24h")),
                  ("cache_hit_24h", "24 h cache hit", "pct", section.get("cache_hit_24h")),
                  ("today", "Today", "tokens", section.get("today")), ("average", "6-day average", "tokens", section.get("average")),
                  ("cost_24h", "24 h cost", "usd", total_cost(section.get("sessions", []))),
                  ("idle_cost_24h", "24 h idle cost ~", "usd", total_cost(section.get("sessions", []), "idle_cost"))])


def total_cost(sessions: List[dict], key: str = "cost") -> Optional[float]:
    costs = [s.get(key) for s in sessions]
    return round(sum(costs), 2) if costs and None not in costs else None


def context_table(rows: List[dict]) -> dict:
    running = [r for r in rows if r["state"] != "off"]
    return table("Running sessions against their sweet spot",
                 [("session", "Session", "text"), ("model", "Model", "text"), ("state", "State", "text"), ("context", "Context", "tokens"),
                  ("spot", "Sweet spot ~", "tokens"), ("of_spot", "Of spot", "pct"), ("window", "Window", "tokens")],
                 [{"id": r.get("name", ""), "session": r.get("name", ""), "model": r.get("model"), "state": r["state"], "context": r.get("context"),
                   "spot": r.get("spot"), "of_spot": round(r["context"] / r["spot"] * 100) if r.get("context") and r.get("spot") else None,
                   "window": r.get("window")}
                  for r in running])


def memory_table(rows: List[dict]) -> dict:
    return table("What each session loads before any work (~), against its role's usual",
                 [("session", "Session", "text"), ("start_load", "Start ~", "tokens"), ("usual", "Usual", "tokens"),
                  ("limit", "Limit", "tokens"), ("notes_saved", "Notes saved", "flag")],
                 [{"id": r["name"], "session": r["name"], "start_load": r.get("start_load"),
                   "usual": (r.get("start_limit") or {}).get("usual"), "limit": (r.get("start_limit") or {}).get("limit"),
                   "notes_saved": r.get("notes_saved")} for r in rows if r["state"] != "off"])


def said_table(saved: dict) -> dict:
    measures = [("answers", "Your answers today", saved.get("answers")),
                ("not_in_decisions", "Not in the decision log", len(saved.get("not_in_decisions", []))),
                ("beads_opened", "Beads opened today", len(saved.get("beads_opened", []))),
                ("commits", "Commits today", len(saved.get("commits", []))),
                ("saved_without_id", "'Saved' with no id", sum(saved.get("without_id", {}).values())),
                ("guard_blocks", "Stopped by the saved guard", saved.get("blocks", 0))]
    return table("Said today against what lasts", [("measure", "Measure", "text"), ("count", "Count", "count")],
                 [{"id": key, "measure": label, "count": n} for key, label, n in measures])


def disk_table(disk: dict) -> dict:
    rows = [{"id": "volume", "place": disk["volume"], "size": round(disk["total"] / GB, 1), "free": round(disk["free"] / GB, 1)}]
    rows += [{"id": name, "place": name, "size": round(size / GB, 1) if size is not None else None, "free": None}
             for name, size in disk["folders"].items()]
    return table("The data volume and the team's folders (sized every 10 min)",
                 [("place", "Place", "text"), ("size", "Size", "gb"), ("free", "Free", "gb")], rows)


def coordination_table(process: dict) -> dict:
    weeks = [("this_week", "This week", process["this_week"]), ("last_week", "Last week", process.get("last_week", {}))]
    return table("Messages between sessions; duplicates and outside the format target 0",
                 [("week", "Week", "text"), ("messages", "Messages", "count"), ("beads", "Beads", "count"),
                  ("median", "Median per bead", "count"), ("worst", "Worst 10%", "count"), ("duplicates", "Duplicates", "count"),
                  ("duplicate_tokens", "Their tokens", "tokens"), ("outside_format", "Outside format", "count")],
                 [dict({"id": key, "week": label}, **{k: w.get(k) for k in ("messages", "beads", "median", "worst", "duplicates",
                                                                            "duplicate_tokens", "outside_format")})
                  for key, label, w in weeks],
                 [("today_duplicates", "Duplicates today", "count", process.get("today_duplicates")),
                  ("two_holds", "Beads with 2+ HOLDs", "count", len(process.get("two_holds", [])))])


def main_table(gate: GateState) -> dict:
    return table("The last gate on the landing ref", [("commit", "Commit", "text"), ("green", "Green", "flag"),
                                                      ("failing", "Failing", "count"), ("unpushed", "To push", "count")],
                 [{"id": "gate", "commit": gate.commit[:8], "green": gate.green, "failing": gate.failing, "unpushed": gate.unpushed}])


def autopilot_table(today: dict) -> dict:
    return table("What it sent today and its proof",
                 [("time", "Time", "text"), ("session", "Session", "text"), ("kind", "Kind", "text"), ("state", "Proof", "text"),
                  ("cut", "Cut", "tokens")],
                 [{"id": f"{r.get('at', 0):.0f}-{r['session']}", "time": r.get("t", ""), "session": r["session"], "kind": r.get("kind", ""), "state": r["state"],
                   "cut": r.get("cut")} for r in today["rows"]],
                 [("sent", "Sent today", "count", len(today["rows"])), ("done", "Proved", "count", today["done"]),
                  ("cut", "Cut today", "tokens", today["cut"]),
                  ("wrong_clears", "Wrong clears, 7 d", "count", sum(c["wrong"] for c in today.get("clears", [])))])


def clears_table(clears: List[dict]) -> dict:
    """A wrong clear: the session after it read a file of its last task again in its first turns (pg-o6lk)."""
    return dict(table("Autopilot clears and compacts judged, 7 days; 2 wrong clears and the session gets only compact",
                      [("session", "Session", "text"), ("clears", "Clears", "count"), ("right", "Clears right", "count"),
                       ("wrong", "Clears wrong", "count"), ("compacts_right", "Compacts right", "count"),
                       ("compacts_wrong", "Compacts wrong", "count"),
                       ("only_compact", "Only compact", "flag")],
                      [dict(c, id=c["session"]) for c in clears]), id="autopilot.clears")


def landed_table(landed: List[dict]) -> dict:
    return dict(table("Tokens per landed bead (~ its session's tokens between start and close)",
                      [("session", "Session", "text"), ("this_week", "Landed this week", "count"), ("per_bead", "Per bead ~", "tokens"),
                       ("last_week", "Landed last week", "count"), ("per_bead_before", "Per bead before ~", "tokens"),
                       ("rising", "Rising", "flag")],
                      [{"id": b["session"], **{k: b.get(k) for k in ("session", "this_week", "per_bead", "last_week", "per_bead_before",
                                                                    "rising")}} for b in landed]), id="tokens.landed")


def holds_table(holds: Optional[dict]) -> dict:
    """HOLD rate by the sender's context at its GO-REQ, 14 days; a band under the minimum shows no rate."""
    rows = [{"id": f"{m['model']} {b['band']}", "model": m["model"], "band": b["band"], "reviews": b["n"], "holds": b["holds"],
             "rate": b["rate"] if b["enough"] else None} for m in (holds or {}).get("models", []) for b in m["bands"]]
    return dict(table(f"HOLD rate by the sender's context, 14 days; no rate under {(holds or {}).get('min', '?')} reviews",
                      [("model", "Model", "text"), ("band", "Context", "text"), ("reviews", "Reviews", "count"), ("holds", "HOLDs", "count"),
                       ("rate", "Rate", "pct")], rows, [("waiting", "GO-REQs with no verdict", "count", (holds or {}).get("waiting"))]),
                id="tokens.holds")

from typing import Dict, List, Optional

from cockpit.team import role_of_name
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.transcripts.history import History
from cockpit.transcripts.session_stats import SessionStats

WEEK = 7 * 86400
OUTCOME_RULE = "WATCH when the owner marked a decision wrong or a clear lost work (its next session read the old files) in 7 days"
USE_RULE = "WATCH when a session reached Claude Code's own compaction line in 24 h: the sweet-spot rule did not get there first"
ELSEWHERE = ("DECISIONS gaps are under Said vs saved, stale memory under Memory, start-file reads in each session's start "
             "load; quota per finished task and docs against code have their own rows")


def k(tokens: float) -> str:
    return f"{tokens / 1e6:.1f}M" if tokens >= 1e6 else f"{round(tokens / 1000)}k"


def holds_of(history: Optional[History], now: float) -> Dict[str, int]:
    found: Dict[str, int] = {}
    for m in (history.messages if history else []):
        if m.type == "HOLD" and m.t >= now - WEEK:
            name = role_of_name(m.to)
            found[name] = found.get(name, 0) + 1
    return found


def outcomes_light(named: Dict[str, SessionStats], week: Dict[str, dict], history: Optional[History], now: float) -> dict:
    """Design pg-o1sq Q11, per session: tokens per finished task without cache (A), re-reads and clears that lost work
    (B), HOLDs it got (C), the owner's wrong clicks (D), beside the autopilot's decisions; what the re-fit (step 7) reads."""
    holds = holds_of(history, now)
    rows = []
    for name, s in named.items():
        w = week.get(name, {})
        starts = w.get("task_starts", {})
        rows.append({"id": name, "session": name, "tasks": s.tasks_closed,
                     "per_task": round(s.tokens_24h / s.tasks_closed) if s.tasks_closed else None, "re_reads": s.re_reads,
                     "wrong_clears": w.get("wrong_clears", 0), "holds": holds.get(name, 0), "wrong": w.get("wrong", 0),
                     "decisions": ", ".join(f"{kind} {n}" for kind, n in sorted(starts.items())) or "none"})
    wrong, lost = sum(r["wrong"] for r in rows), sum(r["wrong_clears"] for r in rows)
    columns = [("session", "Session", "text"), ("tasks", "Tasks, 24 h", "count"), ("per_task", "Per task", "tokens"),
               ("re_reads", "Re-reads", "count"), ("wrong_clears", "Clears that lost work, 7 d", "count"),
               ("holds", "HOLDs, 7 d", "count"), ("wrong", "Wrong clicks, 7 d", "count"), ("decisions", "TASK starts, 7 d", "text")]
    why = (f"{wrong} decision{'' if wrong == 1 else 's'} marked wrong and {lost} clear{'' if lost == 1 else 's'} that lost work in 7 days. "
           "Red gates are under Main")
    return light("outcomes", "Autopilot outcomes", f"{wrong} wrong, {lost} lost", "watch" if wrong or lost else "ok", "", why + ".",
                 OUTCOME_RULE, "transcripts (24 h), actions.jsonl task_start, wrong_clear and wrong (7 d), HOLD messages (7 d)",
                 table("Outcomes per session: what the autopilot's decisions led to", columns, rows))


def notes_word(row: dict) -> str:
    if not row.get("memory_file"):
        return "no state file"
    return "no turn since its start" if row.get("notes_reread") is None else "yes" if row["notes_reread"] else "no"


def good_use_light(rows: List[dict], named: Dict[str, SessionStats], now: float) -> dict:
    """Design Q13, the measures a session's config changes: cache served against written, writes that expired unused,
    context against its sweet spot, and Claude Code's own compactions."""
    by_name = {r["name"]: r for r in rows}
    table_rows = []
    for name, s in named.items():
        moved = s.cache_read_24h + s.cache_write_24h
        itself = sum(1 for c in s.compactions if c.trigger == "auto" and c.at >= now - 86400)
        table_rows.append({"id": name, "session": name, "served": round(100 * s.cache_read_24h / moved) if moved else None,
                           "expired": s.expired_writes_24h, "over": bool(by_name.get(name, {}).get("over")), "itself": itself,
                           "notes": notes_word(by_name.get(name, {}))})
    read, written = sum(s.cache_read_24h for s in named.values()), sum(s.cache_write_24h for s in named.values())
    expired = sum(s.expired_writes_24h for s in named.values())
    hit = [r["session"] for r in table_rows if r["itself"]]
    share = round(100 * read / (read + written)) if read + written else None
    value = f"{share}% from cache, {k(expired)} expired" if share is not None else "nothing read"
    lines = [f"{share}% of the cache traffic of 24 h was served from cache; {k(expired)} written was never read (heuristic)"
             if share is not None else "No cache traffic in 24 h"]
    if hit:
        lines.append(f"Reached Claude Code's own compaction line: {', '.join(hit)}")
    columns = [("session", "Session", "text"), ("served", "From cache %", "count"), ("expired", "Expired unused", "tokens"),
               ("over", "Over its sweet spot", "flag"), ("itself", "Compacted by itself, 24 h", "count"),
               ("notes", "State file re-read at its last start", "text")]
    return light("good_use", "Good use", value, "watch" if hit else "ok", "", ". ".join(lines + [ELSEWHERE]) + ".", USE_RULE,
                 "transcripts (24 h): cache reads and writes per request, the gap to the next request, compact boundaries",
                 table("Cache and context per session, 24 h", columns, table_rows))

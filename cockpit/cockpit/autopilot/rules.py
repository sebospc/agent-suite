from typing import Dict, List, Optional, Set

from cockpit.autopilot.compact_text import compact_text
from cockpit.autopilot.task_start import task_start
from cockpit.autopilot.turn_end import TURN_END, just_finished, turn_line
from cockpit.thresholds import Thresholds

# docs/REQUIREMENTS.md "Autopilot rules"; on by themselves (the owner, 2026-10-16: "debe ser autobalanceado").
SPOT = "Compact idle sessions over their sweet spot"
# Removed 2026-10-22 (panels f68cd6 to b31e2b): Claude Code's own window, which the autopilot sets just under the 100k
# step (window_step.py), already compacts Haiku there; the guard on top only added a compaction every 3 minutes. Kept
# to read the verdicts of its past compactions in actions.jsonl.
HAIKU = "Keep Haiku sessions under 100k"
CEILING = "Compact at the next finished turn over the ceiling"
CLEAR_AT_END = "Clear at task end"


def nothing_to_lose(row: dict) -> bool:
    """Its notes were saved during its last turn, or it holds no bead in progress whose work a clear could drop;
    and, for brain, every answer of the owner is already in the decision log, since a clear forgets that it still owes them."""
    saved = row["notes_saved"] is True or (row["notes_saved"] is None and not row["holds"])
    return saved and not row.get("unsaved_answers")


def background_why(row: dict) -> str:
    """A compaction or clear drops the context a background task reports back to, and a restart kills it."""
    return f"its pane shows {row['background']} running, so it is not compacted or cleared until they finish"


def not_saved_why(row: dict) -> str:
    if row.get("unsaved_answers"):
        return f"the owner's answer {', '.join(row['unsaved_answers'])} is not in the decision log yet"
    if row.get("notes_file"):
        return f"its state file {row['notes_file']} has not changed since its last turn started"
    return "its notes were not saved since its last turn started"


def idle_seconds(row: dict, now: float) -> float:
    return now - row["last_turn_at"] if row["state"] == "idle" and row["last_turn_at"] else 0.0


def stuck_above(row: dict, line: float) -> bool:
    """A compaction would land at or above the line anyway (its base is that big), so sending one loops forever."""
    return bool(row.get("base")) and row["base"] >= line


def thrashing(row: dict, line: Optional[float]) -> bool:
    """COMPACTION.md rule 8: each of its last two compactions left it at or above the line it is compacted at, so
    another one frees nothing; raise its window or clear it instead."""
    refills = row.get("refills") or []
    return line is not None and len(refills) == 2 and all(r is not None and r >= line for r in refills)


def compaction_line(row: dict, guard: float) -> Optional[float]:
    return guard if row.get("haiku_guarded") else row.get("spot")


def thrash_why(row: dict, guard: float, line: Optional[float] = None) -> str:
    return (f"thrash guard: its last two compactions each left it at {'k, '.join(str(round(r / 1000)) for r in row['refills'])}k, "
            f"at or above {round((line or compaction_line(row, guard)) / 1000)}k, so it is not compacted again; raise its window or clear it")


def turn_wait_why(idle: float, thresholds: Thresholds) -> str:
    gap = thresholds.value("turn_end_gap_seconds")
    return f"its turn ended {round(idle)} s ago; it compacts once idle {gap} s" if idle < gap else ""


def compaction(rule: str, row: dict, reason: str) -> dict:
    return {"session": row["name"], "rule": rule, "kind": "compact", "text": compact_text(row), "level": "", "reason": reason}


def compaction_due(row: dict, idle: float, thresholds: Thresholds, read_gap: float = 0) -> bool:
    """Q8 rows 5 to 7: with no TASK coming, a compaction waits until just before its cache expires, since a TASK that
    arrives first decides with more known (rows 1 to 4). Past expiry it would pay full price, so the next TASK decides.
    An unknown cache life keeps the plain idle wait."""
    ttl = row.get("cache_ttl")
    if not ttl:
        return idle >= thresholds.value("autopilot_idle_minutes") * 60
    return compaction_starts(ttl, thresholds, read_gap) <= idle < ttl


def compaction_starts(ttl: float, thresholds: Thresholds, read_gap: float = 0) -> float:
    """Half a 5-minute cache at most, so a short cache still gets its compaction in time. Earlier by the gap between
    the cockpit's last two reads: with 17 minutes between reads the margin's window fell between two of them and a
    397k session went cold uncompacted (brain, pg-o1sq relaunch HOLD finding 2)."""
    return max(0.0, ttl - min(thresholds.value("cache_expiry_margin_minutes") * 60, ttl / 2) - read_gap)


def on_arrival(row: dict, task: dict, line: Optional[float], now: float, only_compact: Set[str]) -> dict:
    """The case table's pick, unless a clear could lose unsaved work, or another compaction would free nothing.
    Unsaved notes block a clear only: a compaction's summary keeps the unsaved work (brain, pg-o1sq finding 3 answer).
    Over its line the clear becomes a compaction, since it is never kept at that size."""
    choice = task_start(row, task, line, idle_seconds(row, now), only_compact)
    if choice["kind"] == "clear" and not nothing_to_lose(row):
        if line is not None and (row["context"] or 0) >= line:
            choice = dict(choice, kind="compact", text=compact_text(row),
                          reason=f"{choice['reason']}; compacted instead of cleared: {not_saved_why(row)}, and a compaction's summary keeps it")
        else:
            return dict(choice, kind="keep", text="", reason=f"{choice['reason']}; kept instead: {not_saved_why(row)}")
    if choice["kind"] in ("compact", "clear") and row.get("background"):
        return dict(choice, kind="keep", text="", reason=f"{choice['reason']}; kept instead: {background_why(row)}")
    if choice["kind"] == "compact" and (thrashing(row, line) or stuck_above(row, line)):
        return dict(choice, kind="keep", text="", reason=f"{choice['reason']}; kept instead: another compaction would leave it over its line")
    return choice


def decide(rows: List[dict], pending: Set[str], thresholds: Thresholds, now: float, arriving: Optional[Dict[str, dict]] = None,
           only_compact: Set[str] = frozenset(), read_gap: float = 0, finished: Optional[Dict[str, str]] = None,
           keep_warm: Optional[Dict[str, dict]] = None) -> List[dict]:
    """What the autopilot sends now, at most one control per session. A session with a control still waiting for its
    proof is left alone, so nothing that did not show is ever sent twice. arriving: per session, the TASK the courier
    types next, not decided yet; its choice may be keep, which types nothing. keep_warm: per session, the keep-warm
    probe's verdict (cockpit/autopilot/keep_warm.py): a probe is sent, or nothing at all (hold), or the rules below decide."""
    guard = thresholds.value("haiku_step_tokens") * thresholds.value("haiku_guard_pct") / 100
    chosen = []
    for row in rows:
        if row["name"] in pending or row["state"] != "idle" or not row["pane"]:
            continue
        # No turn read yet: its transcript is not read (the first read after a start) or it has none; either way
        # nothing is known about it, so nothing is sent (brain's J7).
        if row["last_turn_at"] is None:
            continue
        line = compaction_line(row, guard)
        task = (arriving or {}).get(row["name"])
        if task:
            chosen.append(on_arrival(row, task, line, now, only_compact))
            continue
        context = row["context"] or 0
        bead = (finished or {}).get(row["name"])
        if bead and not row["holds"] and nothing_to_lose(row) and row["name"] not in only_compact and not row.get("background"):
            chosen.append({"session": row["name"], "rule": CLEAR_AT_END, "kind": "clear", "text": "/clear", "level": "", "bead": bead,
                           "reason": f"{bead} closed, idle, its notes saved: its next task starts fresh"})
            continue
        warm = (keep_warm or {}).get(row["name"])
        if warm and warm["act"] == "probe":
            chosen.append(warm["choice"])
        if warm and warm["act"] in ("probe", "hold"):
            continue
        choice = None
        at_turn_end = turn_line(row, thresholds)
        if not thrashing(row, line) and not row.get("background"):
            # Unsaved notes hold neither compaction: waiting for them is how a session misses the window and goes cold
            # at full size, and the summary keeps the unsaved work (brain, pg-o1sq finding 3
            # answer). Nor do the owner's answers still missing from the decision log: panel.json keeps his exact words, and
            # the hold let brain grow to 400k on 2026-10-22 (panels f68cd6 to b31e2b). They still block a clear.
            if row.get("ceiling") and context >= row["ceiling"]:
                # A session that works all day is never idle long enough for the expiry window (pg-45v5 ruling).
                choice = compaction(CEILING, row, f"{round(context / 1000)}k over its ceiling of {round(row['ceiling'] / 1000)}k "
                                                  f"(sweet spot {round(row['spot'] / 1000)}k); its turn just ended")
            elif (at_turn_end and context >= at_turn_end and just_finished(idle_seconds(row, now), thresholds)
                  and not thrashing(row, at_turn_end) and not stuck_above(row, at_turn_end)):
                choice = compaction(TURN_END, row, f"{round(context / 1000)}k over its turn line of {round(at_turn_end / 1000)}k "
                                                   f"(sweet spot {round(row['spot'] / 1000)}k); its turn ended {round(idle_seconds(row, now))} s ago")
            elif row["over"] and compaction_due(row, idle_seconds(row, now), thresholds, read_gap):
                choice = compaction(SPOT, row, f"{round(context / 1000)}k over its sweet spot of {round(row['spot'] / 1000)}k, "
                                               f"idle {round(idle_seconds(row, now) / 60)} m{expiry_note(row)}")
        if choice:
            chosen.append(choice)
    return chosen


def expiry_note(row: dict) -> str:
    return f", just before its {round(row['cache_ttl'] / 60)} m cache expires" if row.get("cache_ttl") else ""


def spot_wait_why(row: dict, idle: float, thresholds: Thresholds, read_gap: float = 0) -> str:
    ttl = row.get("cache_ttl")
    if not ttl:
        needed = thresholds.value("autopilot_idle_minutes") * 60
        return f"idle {round(idle / 60)} m of the {round(needed / 60)} m it waits" if idle < needed else ""
    if idle >= ttl:
        return f"its {round(ttl / 60)} m cache expired, so a compaction would pay full price; its next TASK decides"
    if idle < compaction_starts(ttl, thresholds, read_gap):
        return (f"idle {round(idle / 60)} m; it compacts at {round(compaction_starts(ttl, thresholds, read_gap) / 60)} m, just before its "
                f"{round(ttl / 60)} m cache expires, unless a TASK comes first")
    return ""


def skipped(rows: List[dict], pending: Set[str], thresholds: Thresholds, now: float, read_gap: float = 0) -> List[dict]:
    """Sessions one rule is about, left alone this read, each with the reason (shown under Background jobs, so a
    session over its sweet spot that is not compacted says why)."""
    guard = thresholds.value("haiku_step_tokens") * thresholds.value("haiku_guard_pct") / 100
    found = []
    for row in rows:
        line = turn_line(row, thresholds)
        over_turn_line = bool(line) and (row["context"] or 0) >= line
        if not row["over"] and not over_turn_line:
            continue
        idle = idle_seconds(row, now)
        turn_end = over_turn_line and idle < thresholds.value("turn_end_window_minutes") * 60
        rule = TURN_END if turn_end else SPOT
        why = ("its last control still waits for its proof" if row["name"] in pending
               else thrash_why(row, guard) if thrashing(row, compaction_line(row, guard))
               else thrash_why(row, guard, line) if turn_end and thrashing(row, line)
               else "busy, so it waits for the turn to end" if row["state"] == "busy"
               else background_why(row) if row.get("background")
               else f"it is {row['state']}" if row["state"] != "idle"
               else "it runs in no herdr pane" if not row["pane"]
               else turn_wait_why(idle, thresholds) if turn_end
               else spot_wait_why(row, idle, thresholds, read_gap) if row["over"]
               else "")
        if why:
            found.append({"session": row["name"], "rule": rule, "why": why})
    return found


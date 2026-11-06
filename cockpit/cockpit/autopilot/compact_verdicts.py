from typing import Callable, List

from cockpit.autopilot.rules import HAIKU
from cockpit.transcripts.refill import REFILL_WINDOW_S

COMPACT_MATCH_S = 15 * 60  # a sent /compact is the session's next compact_boundary within this


def judge_compacts(records: List[dict], rows: List[dict], now: float, write: Callable[[dict], None], log: Callable[[str], None]) -> None:
    """A compaction is wrong when its recovery span cost more than the cut saved (row compaction_costs); a Haiku one
    when it was back at 95% of its size within 15 minutes, since it freed nothing that lasted. Logged once."""
    haiku = {r.get("id") for r in records if r.get("event") == "sent" and r.get("kind") == "compact"
             and (str(r.get("reason", "")).startswith(HAIKU) or "haiku" in str(r.get("model_id", "")))}
    # Until 2026-10-22 every Haiku guard compaction was marked right unmeasured (panels f68cd6 to b31e2b); those
    # verdicts carry no refilled_s, so they are judged again, and the latest verdict per compaction counts.
    judged = {r.get("id") for r in records if r.get("event") in ("right_compact", "wrong_compact")
              and (r.get("id") not in haiku or "refilled_s" in r)}
    by_name = {r["name"]: r for r in rows}
    refilled = 0
    for sent in records:
        if sent.get("kind") != "compact" or sent.get("event") != "sent" or sent.get("origin") != "autopilot" or sent.get("id") in judged:
            continue
        at = float(sent["t"])
        cost = next((c for c in (by_name.get(sent["session"]) or {}).get("compaction_costs") or []
                     if at <= c["at"] <= at + COMPACT_MATCH_S), None)
        if cost is None:
            continue
        if sent["id"] in haiku:
            if cost["refilled_s"] is None and now < cost["at"] + REFILL_WINDOW_S:
                continue
            event = "wrong_compact" if cost["refilled_s"] is not None else "right_compact"
            refilled += event == "wrong_compact"
        elif cost["recovery"] is None:
            continue
        else:
            event = "right_compact" if cost["recovery"] <= cost["saved"] else "wrong_compact"
            if event == "wrong_compact":
                log(f"autopilot: wrong compact of {sent['session']}: its recovery cost {cost['recovery']} against {cost['saved']} saved")
        write({"t": now, "event": event, "origin": "autopilot", "id": sent["id"], "session": sent["session"],
               "recovery": cost["recovery"], "saved": cost["saved"], "refilled_s": cost["refilled_s"]})
        judged.add(sent["id"])
    if refilled:
        log(f"autopilot: {refilled} Haiku compaction(s) judged wrong: back at 95% of their size within 15 min")

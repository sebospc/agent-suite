import math
from typing import Callable, Dict, List, Optional, Tuple

from cockpit.team import role_of_name

MIN_SAMPLES = 10
MIN_LABELS = 20      # labelled TASK starts before Jev's cut-off moves
SETTLED_S = 86400    # a decision with no wrong mark after a day counts as right
CUTOFFS = [round(0.30 + 0.05 * i, 2) for i in range(13)]  # 0.30 to 0.90
# A fit: (its value, how many samples, what it was fitted from), or None while there are too few samples.
Fit = Optional[Tuple[float, int, str]]


def percentile(values: List[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(share * len(ordered)) - 1)]


def expiry_margin(records: List[dict], samples: dict, current: float) -> Fit:
    """docs/CALIBRATION.md: the margin that lands 95% of the autopilot's compactions before the cache expires: how
    long a /compact took to show its compact_boundary, read at its 95th percentile, plus one read of 30 s. Only a proof
    with its boundary's own time counts: the record's time is late when the cockpit was down (11 min on 2026-10-18)."""
    sent = {r["id"]: r["t"] for r in records if r.get("event") == "sent" and r.get("origin") == "autopilot" and r.get("kind") == "compact"}
    took = [(r["proved_at"] - sent[r["id"]]) / 60 for r in records if r.get("event") == "done" and r.get("id") in sent and r.get("proved_at")]
    if len(took) < MIN_SAMPLES:
        return None
    return math.ceil(percentile(took, 0.95) + 0.5), len(took), f"95th percentile of {len(took)} compactions' time to their proof, plus one read"


MIN_GAPS = 100


def recovery_idle_gap(records: List[dict], samples: dict, current: float) -> Fit:
    """docs/CALIBRATION.md: the gap longer than 99% of the team's gaps inside a turn, in whole minutes; a longer one is a
    new prompt or a cold cache, not recovery after a compaction."""
    gaps = samples.get("turn_gaps") or []
    if len(gaps) < MIN_GAPS:
        return None
    return max(1, math.ceil(percentile(gaps, 0.99) / 60)), len(gaps), f"99th percentile of {len(gaps)} gaps inside a turn, 24 h"


# A change inside a decision's outcome window that could explain its outcome as well as the decision (owner b289d0 C).
CONFOUNDING_KINDS = ("model", "effort", "relaunch")


def labelled_starts(records: List[dict], now: float) -> List[Tuple[float, bool]]:
    return label_rows(records, now)[0]


def label_rows(records: List[dict], now: float) -> Tuple[List[Tuple[float, bool]], int]:
    """(Jev's carry score, whether carrying was right) for each measured TASK start that did what Jev's bead verdict
    said: kept or compacted when it carried, cleared when it did not, and how many more were confounded. Wrong: the
    owner's wrong click on it, or its clear's next session read the old files again; right: a day without either. A
    keep or clear for another reason (no verdict, a held bead, shared folders) says nothing about Jev, so it is left
    out; so is one whose model, effort, plugins or task changed inside its outcome window (pg-6inz)."""
    wrong = {r.get("of") for r in records if r.get("event") == "wrong"} | {r.get("id") for r in records if r.get("event") == "wrong_clear"}
    found, confounded = [], 0
    for r in records:
        scores = r.get("scores") or {}
        if r.get("event") != "task_start" or "needs_history" not in scores or "related" not in scores:
            continue
        carry_score = max(scores["needs_history"], scores["related"])
        carried = r["action"] != "clear"
        if (carry_score >= r.get("yes", 0.6)) != carried or r.get("case") not in (2, 3, 4):
            continue
        marked = r.get("control") in wrong or f"task:{r['task']}" in wrong
        if not marked and now - r["t"] < SETTLED_S:
            continue
        if confounding(r, records):
            confounded += 1
            continue
        found.append((carry_score, carried != marked))  # wrong flips what was right
    return found, confounded


def confounding(start: dict, records: List[dict]) -> str:
    """What changed in its session inside its outcome window, from the TASK start to its session's next TASK start or a
    day, whichever comes first: a model, effort or plugin relaunch control, a TASK typed by the sender's fallback (no
    TASK start decided it), its process starting again, or Claude Code's auto-compaction (session_changes.py). "" when
    nothing did."""
    session = role_of_name(start.get("session") or "")
    if not session:
        return ""
    at = lambda r: r.get("at", r.get("t", 0))  # a change the cockpit saw later is logged with its own time
    mine = [r for r in records if role_of_name(r.get("session") or "") == session and at(r) > start["t"]]
    end = min([at(r) for r in mine if r.get("event") == "task_start"] + [start["t"] + SETTLED_S])
    for r in (r for r in mine if at(r) < end):
        if r.get("event") == "sent" and r.get("kind") in CONFOUNDING_KINDS:
            return f"a {r['kind']} control"
        if r.get("event") == "task_delivered" and r.get("via") == "fallback":
            return "a TASK typed by fallback"
        if r.get("event") in ("process_started", "auto_compacted"):
            return {"process_started": "its process started again", "auto_compacted": "Claude Code compacted it"}[r["event"]]
    return ""


def jev_cutoff(records: List[dict], samples: dict, current: float) -> Fit:
    """docs/CALIBRATION.md: the cut-off that would have got most labelled TASK starts right; on a tie, the one nearest
    the current value. The session verdict reads the same cut-off."""
    labelled, confounded = label_rows(records, samples.get("now", 0.0))
    if len(labelled) < MIN_LABELS:
        return None
    errors = lambda c: sum(1 for score, carry_right in labelled if (score >= c) != carry_right)
    best = min(CUTOFFS, key=lambda c: (errors(c), abs(c - current)))
    return best, len(labelled), (f"{errors(best)} of {len(labelled)} measured TASK starts wrong at {best:g}"
                                 f"{f'; {confounded} confounded left out' if confounded else ''}")


# The learned numbers that have a fitter; every other one waits for its data (Q14; brain: the quota weights stay set
# until quota per finished task is measured).
FITTERS: Dict[str, Callable[[List[dict], dict, float], Fit]] = {"cache_expiry_margin_minutes": expiry_margin,
                                                                 "jev_yes_probability": jev_cutoff,
                                                                 "recovery_idle_gap_minutes": recovery_idle_gap}

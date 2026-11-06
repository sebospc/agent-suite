from collections import Counter
from typing import Dict, List

from cockpit.transcripts.history import PeerMessage

WEEK = 7 * 86400


def percentile(values: List[int], share: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))] if ordered else 0


def duplicates(messages: List[PeerMessage], window_s: float) -> List[PeerMessage]:
    """The same body received again within the window, by the same or another session: the second and later copies
    (the project's WORKFLOW: one event, one message, one recipient)."""
    seen: Dict[str, float] = {}
    copies = []
    for message in sorted(messages, key=lambda m: m.t):
        if message.digest in seen and message.t - seen[message.digest] <= window_s:
            copies.append(message)
        else:
            seen[message.digest] = message.t
    return copies


def week_figures(messages: List[PeerMessage], window_s: float) -> dict:
    per_bead = list(Counter(m.bead for m in messages if m.bead).values())
    copies = duplicates(messages, window_s)
    return {"messages": len(messages), "beads": len(per_bead), "median": percentile(per_bead, 0.5),
            "worst": percentile(per_bead, 0.9), "duplicates": len(copies), "duplicate_tokens": sum(m.tokens for m in copies),
            "outside_format": sum(1 for m in messages if not m.in_format)}


def process_line(messages: List[PeerMessage], open_beads: set, window_s: float, now: float) -> dict:
    """Messages per bead and duplicates this week against last week, with the beads that hold 2 HOLDs or more."""
    this = [m for m in messages if now - m.t <= WEEK]
    last = [m for m in messages if WEEK < now - m.t <= 2 * WEEK]
    holds = Counter(m.bead for m in messages if m.type == "HOLD" and m.bead in open_beads)
    today = [m for m in this if now - m.t <= 86400]
    return {"this_week": week_figures(this, window_s), "last_week": week_figures(last, window_s),
            "today_duplicates": len(duplicates(today, window_s)),
            "two_holds": sorted((bead for bead, n in holds.items() if n >= 2), key=lambda b: -holds[b]),
            "holds": dict(holds)}

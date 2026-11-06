from typing import List

from cockpit.idle_cost.idle_gap import IdleGap


def idle_gaps(rows: List[dict], boundaries: List[dict], ttl: float, since: float) -> tuple:
    """The gaps over the cache life that ended after `since`, from a session's main-thread requests."""
    compacted = [b["at"] for b in boundaries]
    found = []
    for before, row in zip(rows, rows[1:]):
        start, end = before["t_last"] or 0, row["t_first"] or 0
        if end < since or end - start <= ttl or not before["context"]:
            continue
        found.append(IdleGap(end - start, before["context"], any(start <= at <= end for at in compacted)))
    return tuple(found)

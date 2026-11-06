from typing import List

REWRITE_SHARE = 0.5  # a request that writes over half its context sent it again, not just its new part
CAUSES = ("expiry", "compact", "clear", "settings change", "unknown")


def rewrites(rows: List[dict], boundaries: List[dict], ttl: float, day_ago: float) -> tuple:
    """(cause, tokens written) of each cache rewrite of 24 h (design pg-45v5, measured from day one). The first request
    of a session is a clear (or a new start); the first after a compact_boundary a compact; one after the cache's life
    an expiry; one whose model or effort differs from the request before a settings change. Anything else (an account
    move, a relaunch, an evicted cache) is unknown."""
    compacted = sorted(b["at"] for b in boundaries)
    found = []
    for index, row in enumerate(rows):
        if (row["t_first"] or 0) < day_ago or not row["context"] or row["write"] < REWRITE_SHARE * row["context"]:
            continue
        found.append((cause_of(rows, index, compacted, ttl), row["write"]))
    return tuple(found)


def cause_of(rows: List[dict], index: int, compacted: List[float], ttl: float) -> str:
    if index == 0:
        return "clear"
    row, before = rows[index], rows[index - 1]
    if any((before["t_last"] or 0) <= at <= (row["t_first"] or 0) for at in compacted):
        return "compact"
    if (row["t_first"] or 0) - (before["t_last"] or 0) > ttl:
        return "expiry"
    if (row["model"], row["effort"]) != (before["model"], before["effort"]):
        return "settings change"
    return "unknown"

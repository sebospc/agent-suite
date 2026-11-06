from typing import List, Optional

# A compaction is undone when the session is back at most of its size within minutes: it freed nothing that lasted.
# The coordinator's compactions were back at 95% of their size within 15 minutes 87% of the time (2026-10-22 report).
REFILL_WINDOW_S = 15 * 60
REFILL_SHARE = 0.95


def refilled_after(after: List[dict], at: float, pre: Optional[int]) -> Optional[float]:
    """Seconds from the compaction to the first request back at REFILL_SHARE of its size within the window, or None."""
    if not pre:
        return None
    back = next((r for r in after if (r["t_first"] or 0) - at <= REFILL_WINDOW_S and r["context"] >= REFILL_SHARE * pre), None)
    return None if back is None else round((back["t_first"] or at) - at, 1)

import statistics
from typing import List, Optional

def start_limit(past: List[int], rise_pct: float) -> Optional[dict]:
    """A role's usual start load over 14 days, and the limit above which its bar turns orange (the owner, 2026-10-16:
    per role, from its own history). None with fewer than 3 starts: no usual yet."""
    if len(past) < 3:
        return None
    usual = statistics.median(past)
    return {"usual": round(usual), "limit": round(usual * (1 + rise_pct / 100)), "starts": len(past)}


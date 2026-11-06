from typing import Iterable, List, Optional

from cockpit.board.bead import Bead
from cockpit.display_time import when


def pause_view(since: Optional[float], commits: Optional[List[dict]], beads: Iterable[Bead], now: float) -> dict:
    """Whether the pause holds: the commits and bead claims made after it (design chat L6). Neither should exist once
    brain's hook is in place; until then the check shows what got through."""
    if since is None:
        return {"paused": False}
    claimed = [b.id for b in beads if b.status == "in_progress" and b.started_at and b.started_at >= since]
    landed = [c["sha"] for c in commits or [] if c["t"] >= since]
    return {"paused": True, "since": when(since, now), "commits": landed, "claims": claimed,
            "commits_read": commits is not None, "holds": not landed and not claimed}

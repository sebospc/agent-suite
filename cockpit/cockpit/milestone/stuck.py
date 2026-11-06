from typing import Dict, Iterable

from cockpit.board.bead import Bead


def stuck_beads(beads: Iterable[Bead], holder_turns: Dict[str, float], now: float, hours: float) -> Dict[str, float]:
    """In-progress beads with no sign of work for `hours`: no bead update and no turn by the session that holds
    it. Sessions rarely comment while working, so the holder's transcript is the better sign (CALIBRATION.md)."""
    found = {}
    for bead in beads:
        if bead.status != "in_progress":
            continue
        stamps = [t for t in (bead.last_update(), holder_turns.get(bead.assignee)) if t]
        if stamps and now - max(stamps) > hours * 3600:
            found[bead.id] = (now - max(stamps)) / 3600
    return found

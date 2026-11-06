from typing import Dict, Iterable, List, Optional

from cockpit.board.bead import Bead
from cockpit.team import Team
from cockpit.transcripts.history import Request

WEEK = 7 * 86400


def bead_window(bead: Bead) -> Optional[tuple]:
    start = bead.started_at or (bead.activity[0] if bead.activity else None)
    return (start, bead.closed_at) if start and bead.closed_at and bead.closed_at > start else None


def spent_on(bead: Bead, requests: Iterable[Request]) -> Optional[dict]:
    """What its holder spent while it was in progress: a session works one task at a time (beads_per_task_session),
    so its tokens in that window are the bead's. Heuristic: a turn for something else in the window counts too."""
    window = bead_window(bead)
    if not window or not bead.assignee:
        return None
    mine = [r for r in requests if r.session == bead.assignee and window[0] <= r.t <= window[1]]
    return {"tokens": sum(r.tokens for r in mine), "no_cache": sum(r.no_cache for r in mine), "turns": len({r.turn for r in mine})}


def landed_beads(beads: Iterable[Bead], requests: List[Request], team: Team, rise_pct: float, now: float) -> List[dict]:
    """Tokens per landed bead, by session, this week against last week (LI13)."""
    weeks: Dict[str, List[list]] = {}
    for bead in beads:
        if bead.status != "closed" or not bead.closed_at or now - bead.closed_at > 2 * WEEK or not team.does_task_work(bead.assignee):
            continue
        spent = spent_on(bead, requests)
        if spent is None:
            continue
        weeks.setdefault(team.role_of(bead.assignee), [[], []])[0 if now - bead.closed_at <= WEEK else 1].append(spent["no_cache"])
    shown = []
    for session, (this, last) in sorted(weeks.items()):
        now_mean = sum(this) / len(this) if this else None
        before = sum(last) / len(last) if last else None
        shown.append({"session": session, "this_week": len(this), "per_bead": round(now_mean) if now_mean else None,
                      "last_week": len(last), "per_bead_before": round(before) if before else None,
                      "rising": bool(now_mean and before and now_mean > before * (1 + rise_pct / 100))})
    return sorted(shown, key=lambda s: -(s["per_bead"] or 0))

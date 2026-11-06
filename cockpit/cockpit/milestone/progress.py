import time
from typing import Dict, List

from cockpit.board.bead import Bead
from cockpit.display_time import day_time
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import MILESTONE_TITLE, BeadTree, short_name, without_asides
from cockpit.team import Team

PACE_DAYS = 14
LOG_DAYS = 7  # the same days as "closed in 7 days" under the bars


def workers(criterion: Bead, criteria: Criteria, in_progress: List[Bead], team: Team, states: Dict[str, str]) -> List[dict]:
    """Who moves this criterion now: its own holder while it is in progress, and the holders of beads in progress
    under it or related to it, each with the live state of its session."""
    beads = ([criterion] if criterion.status == "in_progress" else []) + criteria.linked_work(criterion, in_progress)
    names = sorted({team.role_of(b.assignee) for b in beads if b.assignee})
    return [{"name": n, "state": states.get(n, "off")} for n in names]


def local_day(epoch: float) -> tuple:
    return time.localtime(epoch)[:3]


def pace(beads: List[Bead], now: float) -> List[int]:
    """Beads closed under the milestone on each of the last 14 days, oldest first: whether it really moves."""
    days = [local_day(now - (PACE_DAYS - 1 - i) * 86400) for i in range(PACE_DAYS)]
    closed = [local_day(b.closed_at) for b in beads if b.status == "closed" and b.closed_at]
    return [closed.count(d) for d in days]


def closed_lately(beads: List[Bead], now: float) -> List[dict]:
    """The milestone's log: beads closed under it in the last 7 local days, newest first."""
    days = {local_day(now - back * 86400) for back in range(LOG_DAYS)}
    closed = sorted((b for b in beads if b.status == "closed" and b.closed_at and local_day(b.closed_at) in days),
                    key=lambda b: -b.closed_at)
    return [{"id": b.id, "title": b.title, "at": day_time(b.closed_at), "who": b.assignee or "nobody"} for b in closed]


def roadmap(tree: BeadTree, dod: dict, current: Bead) -> List[dict]:
    """Every numbered milestone not closed yet, in order, with its done criteria closed: where the current one sits
    in what is left (the owner, 2026-10-16: only milestones that are not closed)."""
    numbered = sorted(((int(MILESTONE_TITLE.match(b.title).group(1)), b) for b in tree.by_id.values()
                       if b.is_milestone and b.status != "closed" and MILESTONE_TITLE.match(b.title)), key=lambda pair: pair[0])
    stops = []
    for _, milestone in numbered:
        beads = Criteria(tree, milestone, dod, []).beads()
        stops.append({"id": milestone.id, "name": short_name(milestone), "title": without_asides(MILESTONE_TITLE.sub("", milestone.title)),
                      "current": milestone.id == current.id,
                      "closed": sum(1 for b in beads if b.status == "closed"), "total": len(beads)})
    return stops

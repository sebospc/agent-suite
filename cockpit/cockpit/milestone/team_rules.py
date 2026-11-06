from collections import Counter
from typing import Dict, List, Optional

from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import BeadTree
from cockpit.team import Team
from cockpit.thresholds import Thresholds


def broken_team_rules(tree: BeadTree, criteria: Criteria, team: Team, thresholds: Thresholds,
                      stuck: Optional[Dict[str, float]] = None) -> List[str]:
    """The three team rules no other part of the screen shows, one sentence per break (the owner, 2026-10-16: the
    other four "is the team on Mn?" checks already show as a Needs you row, a tile, a stuck mark and the Main light)."""
    in_progress = [b for b in tree.by_id.values() if b.status == "in_progress"]
    return [*unlinked_found_work(criteria), *over_bead_limit(in_progress, team, thresholds), *unknown_holders(tree, team, stuck or {})]


def unlinked_found_work(criteria: Criteria) -> List[str]:
    unlinked = [b.id for b in criteria.found_work() if b.status == "in_progress" and not set(b.related) & set(criteria.ids)]
    if not unlinked:
        return []
    return [f"found work {', '.join(unlinked)} link{'s' if len(unlinked) == 1 else ''} no done criterion"]


def over_bead_limit(in_progress, team: Team, thresholds: Thresholds) -> List[str]:
    limit = thresholds.value("beads_per_task_session")
    held = Counter(b.assignee for b in in_progress if team.does_task_work(b.assignee))
    over = sorted(((who, n) for who, n in held.items() if n > limit), key=lambda pair: -pair[1])
    return [f"{who} holds {n} beads in progress (limit {limit}{thresholds['beads_per_task_session'].note()})" for who, n in over]


def unknown_holders(tree: BeadTree, team: Team, stuck: Dict[str, float]) -> List[str]:
    """A holder outside the team has no session row, so its stuck beads are named here: nowhere else shows them."""
    held = {}
    for bead in tree.by_id.values():
        if bead.is_open and bead.assignee and not team.is_known_holder(bead.assignee):
            held.setdefault(bead.assignee, []).append(bead.id)
    lines = []
    for who, ids in sorted(held.items(), key=lambda pair: -len(pair[1])):
        stalled = [f"{i} stuck {stuck[i]:.0f} h" for i in sorted(ids) if i in stuck]
        lines.append(f"{who}, not a team session, holds {len(ids)} open ({', '.join(sorted(ids)[:3])}{', ...' if len(ids) > 3 else ''})"
                     + (f", {', '.join(stalled)}" if stalled else ""))
    return lines

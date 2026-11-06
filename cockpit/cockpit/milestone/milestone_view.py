from collections import Counter
from typing import Dict, List, Optional

from cockpit.board.bead import OWNER, Bead
from cockpit.board.board_state import BoardState
from cockpit.display_time import age, day, day_time
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.progress import closed_lately, pace, roadmap, workers
from cockpit.milestone.stuck import stuck_beads
from cockpit.milestone.tree import BeadTree, short_name, without_asides
from cockpit.team import Team
from cockpit.thresholds import Thresholds


def milestone_view(board: BoardState, open_asks: List[dict], team: Team, thresholds: Thresholds, now: float,
                   holder_turns: Optional[Dict[str, float]] = None, session_states: Optional[Dict[str, str]] = None) -> dict:
    tree = BeadTree(board.beads)
    milestone = tree.current_milestone()
    if milestone is None:
        return {"available": False, "error": "No open milestone (a bead of type milestone titled Mn: ...)."}
    criteria = Criteria(tree, milestone, board.dod, open_asks)
    stuck = stuck_beads(board.beads, holder_turns or {}, now, thresholds.value("silent_bead_hours"))
    in_progress = [b for b in board.beads if b.status == "in_progress"]
    name = short_name(milestone)
    found = Counter(b.status for b in criteria.found_work())
    return {
        "available": True, "id": milestone.id, "name": name,
        "title": without_asides(milestone.title), "subline": subline(milestone, criteria),
        "goal": goal_line(board),
        "criteria": criteria_cells(criteria, in_progress, team, session_states or {}),
        "pace": pace(tree.descendants(milestone.id), now),
        "closed_log": closed_lately(tree.descendants(milestone.id), now),
        "roadmap": roadmap(tree, board.dod, milestone),
        "left": [left_row(c, criteria, in_progress, now, stuck.get(c.id)) for c in criteria.open()],
        "found": {"total": sum(found.values()), "closed": found["closed"], "in_progress": found["in_progress"],
                  "open": found["open"], "blocked": found["blocked"]},
        "source": f"{board.source}, dod.json, goal.json, panel.json; read {age(now - board.read_at)} ago",
    }


def subline(milestone: Bead, criteria: Criteria) -> str:
    entry = criteria.entry
    if not entry:
        return f"{milestone.id} · done criteria from bd labels (no dod.json entry)"
    return f"{milestone.id} · done criteria set {entry.get('set', '?')} · approved: {entry.get('approved', 'not recorded')}"


def goal_line(board: BoardState) -> dict:
    goal = board.goal or {}
    if not {"value", "total", "target"} <= set(goal):
        return {"available": False, "error": "goal.json has no value, total and target"}
    return {"available": True, "label": goal.get("label", ""), "value": goal["value"], "total": goal["total"],
            "target": goal["target"], "source": f"{goal.get('source', 'no source given')} (goal.json, changed {day_time(board.goal_read_at)})",
            # Shown only when goal.json carries them: a date the cockpit worked out itself would be an invented number.
            "target_date": goal.get("target_date", ""), "next_eval": goal.get("next_eval", ""), "kind": "measured"}


def criteria_cells(criteria: Criteria, in_progress: List[Bead], team: Team, states: Dict[str, str]) -> dict:
    beads = criteria.beads()
    states = Counter(b.status for b in beads)
    goal_bead = criteria.tree.by_id.get(criteria.goal_id) if criteria.goal_id else None
    return {"total": len(beads), "closed": states["closed"], "in_progress": states["in_progress"],
            "blocked": states["blocked"], "open": states["open"],
            "goal_id": criteria.goal_id, "goal_open": bool(goal_bead and goal_bead.is_open),
            "cells": [{"id": b.id, "state": b.status, "is_goal": b.id == criteria.goal_id, "title": b.title,
                       "workers": workers(b, criteria, in_progress, team, states)} for b in beads]}


def left_row(bead: Bead, criteria: Criteria, in_progress: List[Bead], now: float, stuck_hours: Optional[float] = None) -> dict:
    linked = criteria.linked_work(bead, in_progress)
    asks = criteria.asks_for(bead)
    since = day_time(bead.updated_at)
    if bead.status == "in_progress" and stuck_hours:
        note, amber = f"Stuck: no update and no turn by its holder for {stuck_hours:.0f} h.", True
    elif bead.status == "in_progress":
        note, amber = f"In progress, moved {since}.", False
    elif bead.status == "blocked":
        note = f"Blocked since {since}." + (f" Ask {asks[0]['id']} waits on you." if asks else " No ask names it.")
        amber = not asks
    elif Criteria.waits_on_owner(bead):
        note = f"Open since {day(bead.updated_at)}. It waits for you" + (f"; ask {asks[0]['id']} is on the panel." if asks else ", and there is no ask on the panel.")
        amber = not asks
    elif linked:
        note, amber = f"Open; {', '.join(b.id for b in linked)} in progress on it.", False
    else:
        note, amber = f"Open since {day(bead.updated_at)}. No bead in progress is linked to it.", True
    who = bead.assignee or "nobody"
    if Criteria.waits_on_owner(bead) and bead.assignee != OWNER:
        who = f"you (assigned to {who})"
    return {"id": bead.id, "title": bead.title, "note": note, "amber": amber, "who": who,
            "is_goal": bead.id == criteria.goal_id, "age": age(now - bead.updated_at) if bead.updated_at else ""}

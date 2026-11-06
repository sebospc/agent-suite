from collections import Counter
from typing import List, Optional

from cockpit.board.bead import Bead
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import BeadTree, short_name
from cockpit.words import short_title

ORDER = {"dod": 0, "found": 1, "p0": 2, "next": 3, "off": 4}


def bead_kind(bead: Bead, tree: BeadTree, criteria: Optional[Criteria]) -> str:
    if criteria and bead.id in criteria.ids:
        return "dod"
    if criteria and tree.is_under(bead, criteria.milestone.id):
        return "found"
    if bead.priority == 0:
        return "p0"
    return "next" if criteria and is_next(tree.milestone_of(bead), criteria) else "off"


def is_next(milestone, criteria: Criteria) -> bool:
    """Work under the milestone right after the current one (design chat S4): still off the milestone, but early."""
    try:
        return milestone is not None and int(short_name(milestone)[1:]) == int(short_name(criteria.milestone)[1:]) + 1
    except ValueError:
        return False


def describe(bead: Bead, kind: str, tree: BeadTree, milestone_name: str) -> str:
    if kind == "dod":
        return f"{milestone_name} done criterion"
    if kind == "found":
        return f"{milestone_name} found work"
    if kind == "p0":
        return "P0"
    if kind == "next":
        return f"next milestone {short_name(tree.milestone_of(bead))}, P{bead.priority}"
    return f"{short_name(tree.milestone_of(bead))}, P{bead.priority}"


def working_on(role: str, assignee: str, beads: List[Bead], tree: BeadTree, criteria: Optional[Criteria],
               coordinating: bool, state: str) -> dict:
    milestone_name = short_name(criteria.milestone) if criteria else "the milestone"
    held = [b for b in beads if b.assignee == assignee and b.status == "in_progress"]
    # Parked work is deferred on purpose, so it is no reason to wake a session (team_check.py does the same; brain's F14).
    ready = [b for b in beads if b.assignee == assignee and b.status == "open" and not b.is_parked]
    kinds = sorted(((bead_kind(b, tree, criteria), b) for b in held), key=lambda pair: ORDER[pair[0]])
    if not kinds:
        if coordinating:
            verb = "reviews" if role.startswith("reviewer") else "coordinates"
            return {"bead": "no bead", "tag": f"{verb}, holds no bead", "kind": "role",
                    "line": f"It {verb} and holds no bead, as expected for its role.", "held": []}
        if ready and state == "idle":
            return {"bead": "no bead", "tag": f"idle, {len(ready)} open bead{'s' if len(ready) > 1 else ''} assigned",
                    "kind": "idle", "line": f"Holds no bead in progress, with {len(ready)} open beads assigned.", "held": []}
        return {"bead": "no bead", "tag": "no bead in progress", "kind": "none", "line": "Holds no bead in progress.", "held": []}
    first_kind, first = kinds[0]
    first_label = describe(first, first_kind, tree, milestone_name)
    rest = Counter(group_of(b, k, tree) for k, b in kinds[1:])
    tag = first_label + "".join(f", and {n} {group}{'s' if n > 1 and group.endswith('bead') else ''}" for group, n in rest.items())
    if len(kinds) == 1:
        line = f"Holds {first.id} ({first_label}): {short_title(first.title)}."
    else:
        line = f"Holds {len(kinds)} beads in progress: " + "; ".join(
            f"{b.id} ({describe(b, k, tree, milestone_name)})" for k, b in kinds) + "."
    worst = next((k for k in ("off", "next") if any(kind == k for kind, _ in kinds)), first_kind)
    return {"bead": first.id + (f" +{len(kinds) - 1}" if len(kinds) > 1 else ""), "tag": tag, "kind": worst,
            "line": line, "held": [b.id for _, b in kinds]}


def group_of(bead: Bead, kind: str, tree: BeadTree) -> str:
    return {"dod": "done criterion", "found": "found", "p0": "P0"}.get(kind) or f"{short_name(tree.milestone_of(bead))} bead"

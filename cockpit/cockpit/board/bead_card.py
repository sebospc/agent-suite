from typing import Optional

from cockpit.display_time import day_time
from cockpit.milestone.tree import BeadTree, short_name


def bead_card(tree: BeadTree, bead_id: str) -> Optional[dict]:
    """Everything the board says about one bead, for the owner to open it from any id on the page."""
    bead = tree.by_id.get(bead_id)
    if bead is None:
        return None

    def named(ids):
        return [{"id": i, "title": tree.by_id[i].title if i in tree.by_id else "", "status": tree.by_id[i].status if i in tree.by_id else ""}
                for i in ids]

    children = sorted((b for b in tree.by_id.values() if b.parent == bead.id), key=lambda b: b.id)
    return {
        "id": bead.id, "title": bead.title, "status": bead.status, "priority": f"P{bead.priority}", "type": bead.issue_type,
        "assignee": bead.assignee, "labels": bead.labels, "milestone": short_name(tree.milestone_of(bead)),
        "parent": named([bead.parent] if bead.parent else []), "children": named([b.id for b in children]),
        "related": named(bead.related), "blocked_by": named(bead.blocked_by),
        "description": bead.description, "notes": bead.notes, "close_reason": bead.close_reason,
        "updated": day_time(bead.last_update()),
        "comments": [{"author": c["author"], "text": c["text"], "at": day_time(c["at"])} for c in bead.comments],
    }

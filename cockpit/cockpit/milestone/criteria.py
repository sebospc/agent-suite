import re
from typing import Dict, List, Optional

from cockpit.board.bead import OWNER, Bead
from cockpit.milestone.tree import BeadTree

OWNER_TITLE = re.compile(r"^(owner|you)\b|owner approves|\bapprove your\b", re.IGNORECASE)


class Criteria:
    """The milestone's done criteria: the fixed list in dod.json, else children labeled dod, else
    every child that is not found work (the panel's roadmap.py rules)."""

    def __init__(self, tree: BeadTree, milestone: Bead, dod: dict, open_asks: List[dict]):
        self.tree = tree
        self.milestone = milestone
        entry = (dod.get("milestones") or {}).get(milestone.id) or {}
        children = tree.descendants(milestone.id)
        fixed = [i for i in entry.get("dod") or [] if i in tree.by_id]
        labeled = [b.id for b in children if "dod" in b.labels]
        self.ids: List[str] = fixed or labeled or [b.id for b in tree.children.get(milestone.id, []) if not b.is_nice]
        self.entry = entry
        self.goal_id: Optional[str] = entry.get("bar") if entry.get("bar") in self.ids else None
        self.asks_by_bead: Dict[str, List[dict]] = {}
        for ask in open_asks:
            if ask.get("bead"):
                self.asks_by_bead.setdefault(ask["bead"], []).append(ask)

    def beads(self) -> List[Bead]:
        return [self.tree.by_id[i] for i in self.ids]

    def open(self) -> List[Bead]:
        return [b for b in self.beads() if b.is_open]

    def found_work(self) -> List[Bead]:
        """Work found during the milestone: everything under it that is not a criterion or a step of one."""
        criteria = set(self.ids)
        return [b for b in self.tree.descendants(self.milestone.id)
                if b.id not in criteria and not any(self.tree.is_under(b, c) for c in criteria)]

    def linked_work(self, criterion: Bead, in_progress: List[Bead]) -> List[Bead]:
        """In-progress beads that move this criterion: under it, or with a related dependency on it."""
        return [b for b in in_progress if b.id != criterion.id
                and (criterion.id in b.related or self.tree.is_under(b, criterion.id))]

    def asks_for(self, bead: Bead) -> List[dict]:
        return self.asks_by_bead.get(bead.id, [])

    @staticmethod
    def waits_on_owner(bead: Bead) -> bool:
        return bead.assignee == OWNER or OWNER in bead.labels or bool(OWNER_TITLE.search(bead.title))

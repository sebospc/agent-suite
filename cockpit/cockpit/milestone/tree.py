import re
from collections import defaultdict
from typing import Dict, List, Optional

from cockpit.board.bead import Bead

MILESTONE_TITLE = re.compile(r"^M(\d+)\s*:")
ASIDE = re.compile(r"\s*\([^)]*\)")


def without_asides(title: str) -> str:
    """"M6: REA (https://github.com/morluto/rea) and improvements" reads "M6: REA and improvements", not "M6: REA" (pg-219c)."""
    return " ".join(ASIDE.sub("", title).split())


class BeadTree:
    """Beads indexed by id and by parent, walked recursively (pg-a18q.50.1 is under pg-a18q.50)."""

    def __init__(self, beads: List[Bead]):
        self.by_id: Dict[str, Bead] = {b.id: b for b in beads}
        self.children: Dict[str, List[Bead]] = defaultdict(list)
        for bead in beads:
            if bead.parent:
                self.children[bead.parent].append(bead)

    def descendants(self, bead_id: str) -> List[Bead]:
        found, stack = [], list(self.children.get(bead_id, []))
        while stack:
            bead = stack.pop()
            found.append(bead)
            stack.extend(self.children.get(bead.id, []))
        return found

    def is_under(self, bead: Bead, ancestor_id: str) -> bool:
        seen = set()
        current = bead.parent
        while current and current not in seen:
            if current == ancestor_id:
                return True
            seen.add(current)
            parent = self.by_id.get(current)
            current = parent.parent if parent else None
        return False

    def milestone_of(self, bead: Bead) -> Optional[Bead]:
        seen = set()
        current = self.by_id.get(bead.parent) if bead.parent else None
        while current and current.id not in seen:
            if current.is_milestone:
                return current
            seen.add(current.id)
            current = self.by_id.get(current.parent) if current.parent else None
        return None

    def current_milestone(self) -> Optional[Bead]:
        """The open milestone with the lowest number in its title (Mn: ...)."""
        numbered = [(int(MILESTONE_TITLE.match(b.title).group(1)), b) for b in self.by_id.values()
                    if b.is_milestone and b.is_open and MILESTONE_TITLE.match(b.title)]
        return min(numbered, key=lambda pair: pair[0])[1] if numbered else None


def short_name(milestone: Optional[Bead]) -> str:
    if milestone is None:
        return "no milestone"
    match = MILESTONE_TITLE.match(milestone.title)
    return f"M{match.group(1)}" if match else milestone.id

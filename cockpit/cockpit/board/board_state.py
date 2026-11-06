from dataclasses import dataclass
from typing import List

from cockpit.board.bead import Bead


@dataclass(frozen=True)
class BoardState:
    beads: List[Bead]
    dod: dict
    goal: dict
    goal_read_at: float
    read_at: float
    source: str
    milestone_used: bool = True

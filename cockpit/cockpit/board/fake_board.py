from typing import List

from cockpit.board.bead import Bead
from cockpit.board.board import Board
from cockpit.board.board_state import BoardState


class FakeBoard(Board):
    def __init__(self, beads: List[Bead], dod: dict, goal: dict, read_at: float = 0.0):
        self.state = BoardState(beads=beads, dod=dod, goal=goal, goal_read_at=read_at, read_at=read_at, source="fake board")

    def read(self) -> BoardState:
        return self.state

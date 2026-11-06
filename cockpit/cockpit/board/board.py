from abc import ABC, abstractmethod

from cockpit.board.board_state import BoardState


class Board(ABC):
    """The team's board: beads, the milestone's done criteria (dod.json) and the goal metric (goal.json)."""

    @abstractmethod
    def read(self) -> BoardState:
        """Raises SourceUnavailable when bd or a board file cannot be read."""

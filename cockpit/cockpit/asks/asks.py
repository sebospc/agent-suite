from abc import ABC, abstractmethod

from cockpit.asks.asks_state import AsksState


class Asks(ABC):
    """The owner's panel of asks. answer() is the only write phase 1 makes."""

    @abstractmethod
    def read(self) -> AsksState:
        """Raises SourceUnavailable when panel.json cannot be read."""

    @abstractmethod
    def answer(self, ask_id: str, owner_words: str) -> str:
        """Moves the ask to answered with the owner's words; raises SourceUnavailable when that fails."""

from abc import ABC, abstractmethod
from typing import List


class Grill(ABC):
    """grill-with-ui: one session folder per round, served by its own server, changed only by patch."""

    @abstractmethod
    def create(self, topic: str, intent: str, doc: str) -> str:
        """Returns the new session folder."""

    @abstractmethod
    def patch(self, session: str, change: dict) -> None:
        """Raises SourceUnavailable when the patch is refused."""

    @abstractmethod
    def serve(self, session: str) -> str:
        """Starts (or reuses) the session's page server; returns its url."""

    @abstractmethod
    def sends_after(self, session: str, seq: int) -> List[dict]:
        """The owner's sends from the page, oldest first."""

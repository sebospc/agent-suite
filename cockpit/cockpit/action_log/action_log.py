from abc import ABC, abstractmethod
from typing import List


class ActionLog(ABC):
    """Every control sent and its proved outcome, kept across restarts (CLAUDE.md: the autopilot logs every one)."""

    @abstractmethod
    def append(self, record: dict) -> None:
        """Raises SourceUnavailable when the record could not be written."""

    @abstractmethod
    def since(self, start: float) -> List[dict]:
        """Records with t >= start, oldest first."""

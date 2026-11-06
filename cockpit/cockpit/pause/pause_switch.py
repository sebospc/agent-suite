from abc import ABC, abstractmethod
from typing import Optional


class PauseSwitch(ABC):
    """The team's pause: a mark brain's hook reads to block commits, pushes and bead claims (TEAM_DEPENDENCIES 7)."""

    @abstractmethod
    def since(self) -> Optional[float]:
        """When the team was paused, or None while it runs; raises SourceUnavailable."""

    @abstractmethod
    def set(self, paused: bool, now: float) -> None:
        """Raises SourceUnavailable when the mark could not be written or removed."""

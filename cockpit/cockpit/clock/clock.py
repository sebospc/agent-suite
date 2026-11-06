from abc import ABC, abstractmethod


class Clock(ABC):
    """Core code never reads the time directly, so every age and staleness rule is testable."""

    @abstractmethod
    def now(self) -> float:
        """Epoch seconds."""

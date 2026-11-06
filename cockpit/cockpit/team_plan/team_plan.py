from abc import ABC, abstractmethod
from typing import Dict


class TeamPlan(ABC):
    """team.json: the model, effort and window each session is meant to run with (team dependency 8)."""

    @abstractmethod
    def read(self) -> Dict[str, dict]:
        """Role -> {model, effort, window}; raises SourceUnavailable while team.json does not exist."""

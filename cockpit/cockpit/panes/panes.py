from abc import ABC, abstractmethod
from typing import Dict


class Panes(ABC):
    """A session's own terminal pane: text typed there applies exactly as if the owner typed it, and a busy session
    runs it after its turn (the panel does the same, reference/panel/team-roadmap/hooks/register.tsx)."""

    @abstractmethod
    def type_into(self, pane: str, text: str) -> None:
        """Raises SourceUnavailable when the text could not be delivered."""

    @abstractmethod
    def run_in(self, pane: str, command: str) -> None:
        """Runs a shell command in a pane whose agent has exited; raises SourceUnavailable."""

    @abstractmethod
    def labels(self) -> Dict[str, str]:
        """Pane id -> its label (herdr's label, else its title); raises SourceUnavailable."""

    @abstractmethod
    def notify(self, title: str, body: str) -> None:
        """Shows the owner a notification; raises SourceUnavailable."""

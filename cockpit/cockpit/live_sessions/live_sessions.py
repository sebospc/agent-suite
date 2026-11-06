from abc import ABC, abstractmethod
from typing import List

from cockpit.live_sessions.live_session import LiveSession


class LiveSessions(ABC):
    """Running Claude Code sessions: which pid, pane and cswap account each has, and whether it is busy."""

    @abstractmethod
    def list(self) -> List[LiveSession]:
        """Raises SourceUnavailable when neither the session records nor herdr can be read."""

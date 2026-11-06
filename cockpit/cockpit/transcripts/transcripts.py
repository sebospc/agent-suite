from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

from cockpit.transcripts.history import History
from cockpit.transcripts.session_stats import SessionStats


class Transcripts(ABC):
    """Claude Code transcripts. The format is internal and changes between versions, so only adapters parse it."""

    @abstractmethod
    def stats(self, session_ids: List[str], now: float) -> Dict[str, SessionStats]:
        """Stats per main-thread session id found; raises SourceUnavailable when the folder cannot be read."""

    @abstractmethod
    def daily_tokens(self, day_starts: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Tokens without cache (fresh input and output) yesterday up to this time of day and today so far, and today's
        cache reads and writes, over every session and subagent. day_starts: (yesterday 00:00, today 00:00, now)."""

    @abstractmethod
    def history(self, start: float, now: float, names: Dict[str, str]) -> History:
        """Every named session's requests since start, with who started each turn, and the peer messages received.
        names: session id -> name of the live sessions, for a transcript that carries no title."""

    @abstractmethod
    def daily_totals(self, starts: List[float], now: float) -> List[Tuple[int, int]]:
        """(tokens processed, of which cache reads and writes) on each day that starts at starts[i] (local midnights, oldest first),
        today up to now."""

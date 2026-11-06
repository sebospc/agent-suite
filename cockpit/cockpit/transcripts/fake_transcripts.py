from typing import Dict, List, Tuple

from cockpit.transcripts.history import History
from cockpit.transcripts.session_stats import SessionStats
from cockpit.transcripts.transcripts import Transcripts


class FakeTranscripts(Transcripts):
    def __init__(self, by_session: Dict[str, SessionStats], yesterday: int = 0, today: int = 0, cache_reads: int = 0, days: List[int] = (), history: History = History()):
        self.by_session = by_session
        self.totals = (yesterday, today, cache_reads)
        self.days = list(days)
        self.past = history

    def stats(self, session_ids: List[str], now: float) -> Dict[str, SessionStats]:
        return {i: self.by_session[i] for i in session_ids if i in self.by_session}

    def daily_tokens(self, day_starts: Tuple[float, float, float]) -> Tuple[int, int, int]:
        return self.totals

    def daily_totals(self, starts: List[float], now: float) -> List[Tuple[int, int]]:
        return [d if isinstance(d, tuple) else (d, 0) for d in (self.days or [0] * len(starts))[-len(starts):]]

    def history(self, start: float, now: float, names: Dict[str, str]) -> History:
        return History([r for r in self.past.requests if r.t >= start], [m for m in self.past.messages if m.t >= start],
                       [s for s in self.past.starts if s[1] >= start],
                       [s for s in self.past.review_requests if s.t >= start])

from datetime import datetime, timezone
from typing import List

from cockpit.asks.asks import Asks
from cockpit.asks.asks_state import AsksState


class FakeAsks(Asks):
    def __init__(self, open_asks: List[dict], answered: List[dict], read_at: float = 0.0):
        self.open_asks = list(open_asks)
        self.answered = list(answered)
        self.read_at = read_at

    def read(self) -> AsksState:
        return AsksState(open=list(self.open_asks), answered=list(self.answered), read_at=self.read_at, source="fake panel")

    def answer(self, ask_id: str, owner_words: str) -> str:
        match = [a for a in self.open_asks if a.get("id") == ask_id]
        if not match:
            return f"no open ask {ask_id}"
        self.open_asks.remove(match[0])
        stamp = datetime.fromtimestamp(self.read_at, timezone.utc).isoformat()  # as ask_owner.py stamps it
        self.answered.append(dict(match[0], answer=owner_words, answeredAt=stamp))
        return f"answered {ask_id}"

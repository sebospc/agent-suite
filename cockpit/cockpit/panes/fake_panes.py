from typing import Dict, List, Optional, Tuple

from cockpit.panes.panes import Panes
from cockpit.source_unavailable import SourceUnavailable


class FakePanes(Panes):
    def __init__(self, fails: bool = False, labels: Optional[Dict[str, str]] = None):
        self.typed: List[Tuple[str, str]] = []
        self.fails = fails
        self.named = labels or {}
        self.notified: List[Tuple[str, str]] = []

    def type_into(self, pane: str, text: str) -> None:
        if self.fails:
            raise SourceUnavailable(f"herdr agent prompt {pane}: no such pane")
        self.typed.append((pane, text))

    def run_in(self, pane: str, command: str) -> None:
        if self.fails:
            raise SourceUnavailable(f"herdr pane run {pane}: no such pane")
        self.typed.append((pane, command))

    def notify(self, title: str, body: str) -> None:
        self.notified.append((title, body))

    def labels(self) -> Dict[str, str]:
        return dict(self.named)

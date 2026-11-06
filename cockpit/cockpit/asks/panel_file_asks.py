import json
import os
import subprocess
from typing import Callable, List

from cockpit.asks.asks import Asks
from cockpit.asks.asks_state import AsksState
from cockpit.source_unavailable import SourceUnavailable


class PanelFileAsks(Asks):
    """Reads panel.json; answers only through ask_owner.py, the one writer the owner allows (2026-10-12)."""

    def __init__(self, panel_path: str, ask_owner: List[str], timeout_s: float, now: Callable[[], float]):
        self.panel_path = os.path.expanduser(panel_path)
        self.ask_owner = [os.path.expanduser(part) for part in ask_owner]
        self.timeout_s = timeout_s
        self.now = now

    def read(self) -> AsksState:
        try:
            with open(self.panel_path, encoding="utf-8") as handle:
                panel = json.load(handle)
        except (OSError, ValueError) as error:
            raise SourceUnavailable(f"{self.panel_path}: {error}")
        return AsksState(open=list(panel.get("asks") or []), answered=list(panel.get("answered") or []),
                         read_at=self.now(), source=self.panel_path)

    def answer(self, ask_id: str, owner_words: str) -> str:
        command = self.ask_owner + ["answer", ask_id, owner_words]
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailable(f"ask_owner.py answer {ask_id}: {error}")
        if done.returncode != 0:
            raise SourceUnavailable(f"ask_owner.py answer {ask_id} exited {done.returncode}: {done.stderr.strip()[:200]}")
        return done.stdout.strip()

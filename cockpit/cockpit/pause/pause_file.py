import os
from typing import Optional

from cockpit.pause.pause_switch import PauseSwitch
from cockpit.source_unavailable import SourceUnavailable


class PauseFile(PauseSwitch):
    """A file that exists while the team is paused and holds the epoch it was paused at; brain's hook checks it exists."""

    def __init__(self, path: str):
        self.path = os.path.expanduser(path)

    def since(self) -> Optional[float]:
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, encoding="utf-8") as handle:
                return float(handle.read().strip() or 0) or os.path.getmtime(self.path)
        except (OSError, ValueError):
            return os.path.getmtime(self.path)

    def set(self, paused: bool, now: float) -> None:
        try:
            if paused:
                with open(self.path, "w", encoding="utf-8") as handle:
                    handle.write(f"{now:.0f}\n")
            elif os.path.exists(self.path):
                os.remove(self.path)
        except OSError as error:
            raise SourceUnavailable(f"{self.path}: {error}")

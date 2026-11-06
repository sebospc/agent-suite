from typing import Optional

from cockpit.pause.pause_switch import PauseSwitch


class FakePause(PauseSwitch):
    def __init__(self, since: Optional[float] = None):
        self.at = since

    def since(self) -> Optional[float]:
        return self.at

    def set(self, paused: bool, now: float) -> None:
        self.at = now if paused else None

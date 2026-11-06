from cockpit.clock.clock import Clock


class FixedClock(Clock):
    def __init__(self, now: float):
        self.current = now

    def now(self) -> float:
        return self.current

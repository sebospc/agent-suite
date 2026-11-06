from cockpit.mac.mac import Mac


class FakeMac(Mac):
    def __init__(self, state: dict):
        self.state = state

    def read(self) -> dict:
        return dict(self.state)

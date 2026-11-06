from cockpit.config_guard.config_files import ConfigFiles


class FakeConfigFiles(ConfigFiles):
    def __init__(self, current=None, baseline=None, since=0.0):
        self.state = {"current": current or {}, "baseline": baseline if baseline is not None else (current or {}), "since": since}

    def read(self) -> dict:
        return dict(self.state)

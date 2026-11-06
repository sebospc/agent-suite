from cockpit.disk.disk import Disk


class FakeDisk(Disk):
    def __init__(self, free: int, total: int, folders: dict = None):
        self.state = {"volume": "/fake", "free": free, "total": total, "folders": folders or {}}

    def read(self) -> dict:
        return dict(self.state)

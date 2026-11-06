from typing import List

from cockpit.action_log.action_log import ActionLog


class FakeActionLog(ActionLog):
    def __init__(self):
        self.records: List[dict] = []

    def append(self, record: dict) -> None:
        self.records.append(dict(record))

    def since(self, start: float) -> List[dict]:
        return [r for r in self.records if r.get("t", 0) >= start]

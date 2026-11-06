from typing import Dict, List

from cockpit.grill.grill import Grill


class FakeGrill(Grill):
    def __init__(self):
        self.patches: Dict[str, List[dict]] = {}
        self.sends: Dict[str, List[dict]] = {}

    def create(self, topic: str, intent: str, doc: str) -> str:
        session = f"/fake/grill/{len(self.patches) + 1}"
        self.patches[session] = []
        self.sends[session] = []
        return session

    def patch(self, session: str, change: dict) -> None:
        self.patches[session].append(change)

    def serve(self, session: str) -> str:
        return "http://127.0.0.1:52817/"

    def sends_after(self, session: str, seq: int) -> List[dict]:
        return [s for s in self.sends[session] if s["seq"] > seq]

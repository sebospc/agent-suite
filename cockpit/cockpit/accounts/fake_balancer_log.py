from typing import List, Optional

from cockpit.accounts.balancer_log import BalancerLog
from cockpit.not_set_up_yet import NotSetUpYet


class FakeBalancerLog(BalancerLog):
    def __init__(self, decisions: Optional[List[dict]]):
        self.decisions = decisions

    def since(self, start: float) -> List[dict]:
        if self.decisions is None:
            raise NotSetUpYet("the balancer's decision log does not exist yet (pg-81e3)")
        return [d for d in self.decisions if d["t"] >= start]

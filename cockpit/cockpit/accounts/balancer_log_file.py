import json
import os
from typing import List

from cockpit.accounts.balancer_log import BalancerLog
from cockpit.not_set_up_yet import NotSetUpYet
from cockpit.times import parse_time


class BalancerLogFile(BalancerLog):
    def __init__(self, path: str):
        self.path = os.path.expanduser(path)

    def since(self, start: float) -> List[dict]:
        if not os.path.exists(self.path):
            raise NotSetUpYet("the balancer's decision log does not exist yet (pg-81e3)")
        decisions = []
        with open(self.path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    decision = json.loads(line)
                except ValueError:
                    continue
                stamp = decision.get("t")
                stamp = stamp if isinstance(stamp, (int, float)) else parse_time(stamp)
                if stamp and stamp >= start:
                    decisions.append(dict(decision, t=stamp))
        return decisions

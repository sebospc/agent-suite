from typing import Optional

from cockpit.milestone.milestone_plan import MilestonePlan
from cockpit.milestone.milestone_plan_state import MilestonePlanState


class FakeMilestonePlan(MilestonePlan):
    def __init__(self, dod: dict, goal: dict, goal_read_at: float = 0.0):
        self.state = MilestonePlanState(dod=dod, goal=goal, goal_read_at=goal_read_at)

    def read(self) -> Optional[MilestonePlanState]:
        return self.state

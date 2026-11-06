from typing import Optional

from cockpit.milestone.milestone_plan import MilestonePlan
from cockpit.milestone.milestone_plan_state import MilestonePlanState


class NoMilestonePlan(MilestonePlan):
    def read(self) -> Optional[MilestonePlanState]:
        return None

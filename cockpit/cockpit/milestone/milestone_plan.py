from abc import ABC, abstractmethod
from typing import Optional

from cockpit.milestone.milestone_plan_state import MilestonePlanState


class MilestonePlan(ABC):
    # The milestone's done criteria and goal metric, kept apart from the beads so a project can have beads and no milestone.

    @abstractmethod
    def read(self) -> Optional[MilestonePlanState]:
        # None when the project keeps no milestone; raises SourceUnavailable when its files cannot be read.
        pass

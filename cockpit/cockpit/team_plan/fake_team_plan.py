from typing import Dict, Optional

from cockpit.not_set_up_yet import NotSetUpYet
from cockpit.team_plan.team_plan import TeamPlan


class FakeTeamPlan(TeamPlan):
    def __init__(self, plan: Optional[Dict[str, dict]]):
        self.plan = plan

    def read(self) -> Dict[str, dict]:
        if self.plan is None:
            raise NotSetUpYet("no team.json yet (team dependency 8)")
        return self.plan

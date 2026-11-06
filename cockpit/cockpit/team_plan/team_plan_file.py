import json
import os
from typing import Dict

from cockpit.team import role_of_name
from cockpit.not_set_up_yet import NotSetUpYet
from cockpit.source_unavailable import SourceUnavailable
from cockpit.team_plan.team_plan import TeamPlan


class TeamPlanFile(TeamPlan):
    def __init__(self, path: str):
        self.path = os.path.expanduser(path)

    def read(self) -> Dict[str, dict]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            raise NotSetUpYet(f"no team.json at {self.path} yet (team dependency 8)")
        except (OSError, ValueError) as error:
            raise SourceUnavailable(f"{self.path}: {error}")
        sessions = raw.get("sessions", raw) if isinstance(raw, dict) else {}
        return {role_of_name(role): plan for role, plan in sessions.items() if isinstance(plan, dict)}

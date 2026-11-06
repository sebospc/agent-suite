import json
import os
from typing import Optional

from cockpit.milestone.milestone_plan import MilestonePlan
from cockpit.milestone.milestone_plan_state import MilestonePlanState
from cockpit.source_unavailable import SourceUnavailable


class MilestonePlanFiles(MilestonePlan):
    def __init__(self, folder: str):
        self.folder = os.path.expanduser(folder)

    def read(self) -> Optional[MilestonePlanState]:
        goal_path = os.path.join(self.folder, "goal.json")
        return MilestonePlanState(dod=read_json(os.path.join(self.folder, "dod.json")), goal=read_json(goal_path),
                                  goal_read_at=mtime(goal_path))


def read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise SourceUnavailable(f"{path}: {error}")


def mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0

from dataclasses import dataclass


@dataclass(frozen=True)
class MilestonePlanState:
    dod: dict
    goal: dict
    goal_read_at: float

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GateState:
    """The last verify_commit.sh gate on the landing ref, and the commits it holds that main does not."""
    commit: str
    green: Optional[bool]
    running: bool
    failing: int
    unpushed: Optional[int]
    source: str
    in_flight: bool = True  # False: stack.json holds no commit and no gate, so commit is the pushed head

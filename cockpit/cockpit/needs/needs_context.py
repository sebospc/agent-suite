from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from cockpit.accounts.account import Account

from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import BeadTree
from cockpit.team import Team
from cockpit.thresholds import Thresholds


@dataclass(frozen=True)
class NeedsContext:
    rows: List[dict]
    tree: Optional[BeadTree]
    criteria: Optional[Criteria]
    open_asks: List[dict]
    mentions: dict          # session name -> {beads, asks, commits, saved}: ids named in replies of 24 h, and "saved" with no id
    team: Team
    thresholds: Thresholds
    now: float
    accounts: List[Account] = field(default_factory=list)
    next_pick: str = field(default="")  # the account the balancer chose last, so the next new session lands there
    known_asks: Set[str] = field(default_factory=set)        # every ask id on the panel, open or answered
    known_commits: Optional[Set[str]] = field(default=None)  # None when git could not be asked
    gate: Optional[object] = field(default=None)
    stuck: Dict[str, float] = field(default_factory=dict)   # bead id -> hours without work
    receipt_breaks: List[str] = field(default_factory=list)
    config_drift: List[dict] = field(default_factory=list)   # token tool lines added or removed in settings since the baseline
    config_since: str = field(default="")                    # when that baseline was saved, for the sentence
    tool_failures: List[str] = field(default_factory=list)   # "<session>: <tool>: what its hook said" of 24 h

from dataclasses import dataclass
from typing import Optional

from cockpit.compaction.recovery_mix import RecoveryMix


@dataclass(frozen=True)
class SweetSpotInputs:
    model: str
    ttl_seconds: int
    P: float        # context right after a compaction (summary and rework included)
    F_s: float      # stable cached prefix that survives a compaction
    S: float        # summary tokens kept
    T_s: float      # summary output beyond S (not in transcripts; assumed y)
    g: float        # growth per turn
    g_p90: float
    y: float        # output per turn
    q: float        # share of turns after an idle gap longer than the cache TTL
    kind: str       # measured | provisional | heuristic
    basis: str      # where P, S and the rest came from, in one phrase
    recovery: Optional[RecoveryMix] = None  # R, measured per task kind; None before any span was measured

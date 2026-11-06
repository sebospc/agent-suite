from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryMix:
    """The mean token mix of recent recovery spans of one task kind (docs/COMPACTION.md, R). Kept as tokens so each
    session prices it at its own card."""
    fresh: float
    write: float
    read: float
    out: float
    compactions: int
    kind: str           # the task kind it was measured on, or "fleet"
    provisional: bool   # the fleet value standing in for a kind with too few compactions

    @property
    def tokens(self) -> float:
        return self.fresh + self.write + self.read + self.out

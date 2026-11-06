from dataclasses import dataclass


@dataclass(frozen=True)
class RecoverySpan:
    """The requests a session made after a compaction until it worked again (docs/COMPACTION.md, R): their token mix,
    priced later at the session's own card, and what ended the span."""
    fresh: int
    write: int
    read: int
    out: int
    requests: int
    ended_by: str  # edit | 10 requests | task end | next compaction | idle gap

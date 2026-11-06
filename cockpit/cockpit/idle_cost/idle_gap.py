from dataclasses import dataclass


@dataclass(frozen=True)
class IdleGap:
    """A stretch between two requests of one session longer than its cache life: the next request found the cache gone."""
    seconds: float
    context: int      # tokens the cache held when it went idle: what a rewrite writes and a probe reads
    compacted: bool   # a compact_boundary fell inside it (the session was compacted while idle)

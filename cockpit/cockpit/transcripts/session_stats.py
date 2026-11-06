from dataclasses import dataclass, field
from typing import List, Optional, Set

from cockpit.transcripts.recovery_span import RecoverySpan


@dataclass(frozen=True)
class Compaction:
    at: float
    trigger: str
    pre: Optional[int]
    post: Optional[int]
    first_context: Optional[int]  # P: context of the first request after it
    first_cached: Optional[int]   # F_s: cache read of that request
    recovery: Optional[RecoverySpan] = None  # None while the transcript has not finished its span
    refilled_s: Optional[float] = None  # seconds until it was back at 95% of pre, within 15 min (refill.py); None: it was not


@dataclass(frozen=True)
class SessionStats:
    session_id: str
    title: str
    model: str
    effort: str
    ttl_seconds: int
    context_now: Optional[int]
    floor: Optional[int]          # F: context of the first request
    last_turn_at: Optional[float]
    tokens_24h: int               # without cache: fresh input and output
    growth: List[int]             # recent growth per turn, excluding post-compaction, recovery and cold turns
    outputs: List[int]            # recent output per turn
    gaps: List[float]             # seconds between turns
    compactions: List[Compaction]
    haiku_over_step: int
    mentioned_beads: Set[str] = field(default_factory=set)
    mentioned_asks: Set[str] = field(default_factory=set)
    mentioned_commits: Set[str] = field(default_factory=set)
    saved_without_id: int = 0
    evidence: List[tuple] = field(default_factory=list)  # (time, kind, id, reply line) behind the mentions of 24 h
    started_at: Optional[float] = None  # its first request: a fresh start, a /clear or a resume
    turns: int = 0                      # the prompts that opened a turn
    saved_places: List[str] = field(default_factory=list)  # where its replies of 24 h said they saved something
    start_load: Optional[int] = None    # first request minus its first message (~ heuristic)
    cwd: str = ""
    turn_started_at: Optional[float] = None
    token_tools: Set[str] = field(default_factory=set)       # token tools whose hook ran fine in 24 h (ask 8ccee2)
    tool_failures: List[tuple] = field(default_factory=list)  # (time, tool, what it said) of 24 h: a hook that crashed or timed out
    tasks_closed: int = 0   # bd close calls of 24 h: the finished tasks its tokens are divided by
    task_files: frozenset = frozenset()   # files its last finished task read or changed (pg-o6lk)
    start_modes: frozenset = frozenset()  # writing modes its last start's SessionStart hooks switched on (caveman, adhd)
    skills: frozenset = frozenset()       # skills it invoked with the Skill tool
    start_modes_at: Optional[float] = None  # when its last start's SessionStart hooks ran
    first_reads: frozenset = frozenset()  # files it read in its first turns: after a clear, a hit on task_files is a wrong clear
    last_turns: tuple = ()  # (time, "asked" or "replied", text) of its last few turns, for Jev's session verdict
    cache_read_24h: int = 0     # tokens its requests of 24 h read from the cache
    cache_write_24h: int = 0    # tokens they wrote to it
    expired_writes_24h: int = 0  # written, then the next request came after the cache's life (or none yet): never read
    rewrites_24h: tuple = ()  # (cause, tokens) of each request of 24 h that wrote over half its context (cache_rewrites.py)
    last_read: int = 0    # its last request's cache read, write and context: a keep-warm probe's proof
    last_write: int = 0
    last_context: int = 0
    idle_gaps_24h: tuple = ()  # IdleGap of each stretch of 24 h longer than the cache life (cockpit/idle_cost)
    reads_since_start: Optional[frozenset] = None  # Read paths and Bash commands of its first turns after its last start; None: none yet
    turn_gaps: tuple = ()       # seconds between its requests of 24 h with no new prompt between them: work, not waiting
    hook_outputs: tuple = ()  # (command, time, characters) of each hook's last output in its transcript
    re_reads: int = 0       # Read calls of 24 h on a file it had already read since its last compaction  # the last prompt that was not a tool result or a slash command

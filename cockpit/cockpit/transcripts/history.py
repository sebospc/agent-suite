from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Request:
    """One deduplicated model request of a named session (subagents count for the session that ran them)."""
    t: float
    session: str     # the transcript's title, <prefix><role> when the team launches it with --name
    tokens: int      # processed: input, cache reads and writes, output
    context: int     # 0 for a subagent's request, whose context is not the session's
    origin: str      # who started the turn it belongs to: peer, person, command or own
    turn: str        # one id per turn, so turns can be counted
    read: int = 0    # cache reads among tokens
    out: int = 0     # output among tokens
    write: int = 0   # cache writes among tokens; the rest is fresh input
    model: str = ""  # the request's model, so its cost uses its own price card
    effort: str = ""  # its effort level, for the comparison by effort (pg-45v5)

    @property
    def no_cache(self) -> int:
        """Fresh input and output: the number every token figure shows first (the owner, 56fba6)."""
        return self.tokens - self.read - self.write


@dataclass(frozen=True)
class PeerMessage:
    """A message from another session, as its receiver's transcript shows it."""
    t: float
    to: str
    type: str        # the WORKFLOW type on line 1, "" when line 1 has none
    bead: str
    in_format: bool  # line 1 `<TYPE> <bead> [vN]`, at most 10 lines
    digest: str      # the body's sha256, so the same event sent twice is seen
    tokens: int      # what the turn it started cost the receiver
    keys: dict = field(default_factory=dict)  # sha256, sha, base, tree, go-tree, patch from its key: value lines
    head: str = ""   # line 1's WORKFLOW type even when the line is out of format, as reviews were before 2026-10-14


@dataclass(frozen=True)
class ReviewRequest:
    """A GO-REQ as its sender's transcript shows it: who sent it, when, for which patch, at what context."""
    t: float
    sender: str
    bead: str
    sha256: str
    context: int     # the size of the request that sent it
    model: str       # that request's model (claude-opus-5-5)


@dataclass(frozen=True)
class History:
    requests: List[Request] = field(default_factory=list)
    messages: List[PeerMessage] = field(default_factory=list)
    starts: List[tuple] = field(default_factory=list)  # (session name, time, start load) of each session started in the window
    review_requests: List[ReviewRequest] = field(default_factory=list)

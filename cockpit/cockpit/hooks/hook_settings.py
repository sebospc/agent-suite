from abc import ABC, abstractmethod
from typing import List, Optional


class HookSettings(ABC):
    """The team's Claude Code hooks, read only (the owner, 2026-10-16: "only view and logs"; ~/.claude stays untouched)."""

    @abstractmethod
    def hooks(self) -> List[dict]:
        """{source, event, matcher, command} for every hook in the settings files; raises SourceUnavailable."""

    @abstractmethod
    def log_activity(self, path: str, since: float) -> Optional[dict]:
        """{last, today} of a hook's JSONL log: when it was last written, how many lines since; None when it has none."""

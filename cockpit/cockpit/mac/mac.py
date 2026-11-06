from abc import ABC, abstractmethod


class Mac(ABC):
    """The Mac under the team: memory pressure, processes left behind, and the Claude Code each session runs."""

    @abstractmethod
    def read(self) -> dict:
        """{memory_free_pct, swap_used_mb, orphans: [{pid, age_s, args}], claude_version, session_versions: {session_id: version}};
        raises SourceUnavailable."""

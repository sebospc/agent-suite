from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set

from cockpit.git.gate_state import GateState


class Git(ABC):
    @abstractmethod
    def gate(self) -> GateState:
        """The newest verify_commit.sh log and the landing ref's unpushed commits; raises SourceUnavailable."""

    @abstractmethod
    def known_commits(self, shas: Set[str]) -> Set[str]:
        """The ones that name a commit in any of the team's repos; raises SourceUnavailable."""

    @abstractmethod
    def commits_since(self, start: float) -> List[dict]:
        """{sha, subject, t} on the landing ref since start, newest first; raises SourceUnavailable."""

    @abstractmethod
    def path_changes(self, days: int) -> Dict[str, Dict[str, float]]:
        """Per team repo, each path's last commit time in the last `days`; raises SourceUnavailable."""

    @abstractmethod
    def doc_texts(self, skipped: List[str]) -> Dict[str, Dict[str, str]]:
        """Per team repo, each tracked Markdown doc (docs/, README.md, CLAUDE.md) but the skipped ones (a path, or a
        folder ending in /), as on disk."""

    @abstractmethod
    def committed_text(self, path: str) -> str:
        """A file as the landing ref holds it: committed, so trusted (design chat N20); raises SourceUnavailable."""

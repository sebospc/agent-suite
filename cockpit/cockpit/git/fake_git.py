from typing import Dict, List, Optional, Set

from cockpit.git.gate_state import GateState
from cockpit.git.git import Git


class FakeGit(Git):
    def __init__(self, gate: GateState, commits: Dict[str, float], known: Set[str] = frozenset(),
                 landed: List[dict] = (), files: Optional[Dict[str, str]] = None, changes: Optional[dict] = None,
                 docs: Optional[dict] = None):
        self.state = gate
        self.commits = commits
        self.known = set(known)
        self.landed = list(landed)
        self.files = files or {}
        self.changes = changes or {}
        self.docs = docs or {}

    def path_changes(self, days: int) -> Dict[str, Dict[str, float]]:
        return self.changes

    def doc_texts(self, skipped: List[str]) -> Dict[str, Dict[str, str]]:
        return {repo: {p: t for p, t in docs.items() if p not in skipped} for repo, docs in self.docs.items()}

    def gate(self) -> GateState:
        return self.state

    def known_commits(self, shas: Set[str]) -> Set[str]:
        return {s for s in shas if any(k.startswith(s) for k in self.known)}

    def commits_since(self, start: float) -> List[dict]:
        return [c for c in self.landed if c["t"] >= start]

    def committed_text(self, path: str) -> str:
        return self.files.get(path, "")

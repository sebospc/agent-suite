from dataclasses import dataclass, field
from typing import List, Optional

from cockpit.times import parse_time

OWNER = "owner"


@dataclass(frozen=True)
class Bead:
    id: str
    title: str
    status: str
    priority: int
    issue_type: str
    assignee: str
    labels: List[str]
    parent: Optional[str]
    related: List[str]
    updated_at: Optional[float]
    started_at: Optional[float]
    activity: List[float] = field(default_factory=list)
    description: str = field(default="")
    notes: str = field(default="")
    close_reason: str = field(default="")
    closed_at: Optional[float] = field(default=None)
    blocked_by: List[str] = field(default_factory=list)
    comments: List[dict] = field(default_factory=list)  # {author, text, at}, oldest first
    created_at: Optional[float] = field(default=None)

    @staticmethod
    def from_export(raw: dict) -> "Bead":
        """One line of `bd export --all` (or `bd list --json`, which names the parent directly)."""
        dependencies = raw.get("dependencies") or []
        parents = [d.get("depends_on_id") for d in dependencies if d.get("type") == "parent-child"]
        related = [d.get("depends_on_id") for d in dependencies if d.get("type") == "related"]
        blocked_by = [d.get("depends_on_id") for d in dependencies if d.get("type") == "blocks" and d.get("depends_on_id")]
        comment_times = [parse_time(c.get("created_at")) for c in raw.get("comments") or []]
        try:
            priority = int(raw.get("priority", 2))
        except (TypeError, ValueError):
            priority = 2
        return Bead(
            id=raw["id"], title=raw.get("title") or "", status=raw.get("status") or "open",
            priority=priority, issue_type=raw.get("issue_type") or "task",
            assignee=raw.get("assignee") or "", labels=list(raw.get("labels") or []),
            parent=raw.get("parent") or (parents[0] if parents else None),
            related=[r for r in related if r], updated_at=parse_time(raw.get("updated_at")),
            started_at=parse_time(raw.get("started_at")),
            activity=sorted(t for t in comment_times if t is not None),
            description=raw.get("description") or "", notes=raw.get("notes") or "", close_reason=raw.get("close_reason") or "",
            closed_at=parse_time(raw.get("closed_at")), created_at=parse_time(raw.get("created_at")),
            blocked_by=blocked_by,
            comments=sorted(({"author": c.get("author") or "", "text": c.get("text") or "", "at": parse_time(c.get("created_at"))}
                             for c in raw.get("comments") or []), key=lambda c: c["at"] or 0),
        )

    @property
    def is_open(self) -> bool:
        return self.status != "closed"

    @property
    def is_nice(self) -> bool:
        return "nice" in self.labels

    @property
    def is_parked(self) -> bool:
        """Deferred on purpose (team_check.py reads the same title mark), so it is nobody's next task."""
        return "Parked" in self.title

    @property
    def is_milestone(self) -> bool:
        return self.issue_type == "milestone"

    def last_update(self) -> Optional[float]:
        stamps = [t for t in [self.updated_at, self.started_at] + self.activity if t is not None]
        return max(stamps) if stamps else None

from dataclasses import dataclass
from typing import List, Tuple

# Each project names its sessions <prefix><role> (.cockpit.json team.session_prefix). Old prefixes are read only:
# transcripts and sessions launched before a rename still carry them (team.legacy_prefixes).
PREFIX = "agent-"
LEGACY_PREFIXES: Tuple[str, ...] = ()


def configure(prefix: str, legacy_prefixes: List[str]) -> None:
    global PREFIX, LEGACY_PREFIXES
    PREFIX, LEGACY_PREFIXES = prefix, tuple(legacy_prefixes)


def session_name(role: str) -> str:
    return PREFIX + role


def all_prefixes() -> Tuple[str, ...]:
    return (PREFIX, *LEGACY_PREFIXES)


def names_of(role: str) -> Tuple[str, ...]:
    return tuple(prefix + role for prefix in all_prefixes())


def role_of_name(name: str) -> str:
    for prefix in all_prefixes():
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


@dataclass(frozen=True)
class Team:
    """Who the team is (.cockpit.json team)."""
    roles: List[str]
    coordinating: List[str]
    known_holders: List[str]

    def session_name(self, role: str) -> str:
        return session_name(role)

    def role_of(self, assignee: str) -> str:
        return role_of_name(assignee)

    def is_session(self, assignee: str) -> bool:
        return self.role_of(assignee) in self.roles and assignee.startswith(all_prefixes())

    def is_known_holder(self, assignee: str) -> bool:
        return self.is_session(assignee) or assignee in self.known_holders

    def does_task_work(self, assignee: str) -> bool:
        return self.is_session(assignee) and self.role_of(assignee) not in self.coordinating

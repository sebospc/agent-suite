from abc import ABC, abstractmethod
from typing import Optional


class RoleMemory(ABC):
    """The state file a role session keeps instead of a bead (memory/project_<role>_state.md), read only."""

    @abstractmethod
    def state_file(self, role: str, cwd: str = "") -> str:
        """The file's name for the role, as the session in cwd spells it."""

    @abstractmethod
    def modified_at(self, cwd: str, role: str) -> Optional[float]:
        """When the role's state file last changed for a session running in cwd; None when it does not exist."""

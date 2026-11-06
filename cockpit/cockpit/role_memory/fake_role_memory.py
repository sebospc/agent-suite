from typing import Dict, Optional

from cockpit.role_memory.role_memory import RoleMemory


class FakeRoleMemory(RoleMemory):
    def __init__(self, by_role: Optional[Dict[str, float]] = None):
        self.by_role = by_role or {}

    def state_file(self, role: str, cwd: str = "") -> str:
        return f"project_{role}_state.md"

    def modified_at(self, cwd: str, role: str) -> Optional[float]:
        return self.by_role.get(role)

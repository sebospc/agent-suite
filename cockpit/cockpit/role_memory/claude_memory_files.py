import os
from typing import Optional

from cockpit.role_memory.role_memory import RoleMemory


class ClaudeMemoryFiles(RoleMemory):
    """The project's auto memory folder sits under the transcripts folder, named after the session's folder (cwd with
    / and . as -). Only stat is called: nothing under ~/.claude is ever written."""

    def __init__(self, transcripts: str):
        self.transcripts = os.path.expanduser(transcripts)

    def state_file(self, role: str, cwd: str = "") -> str:
        """Sessions spell a hyphenated role their own way (project_reviewer2_state.md, project_shaping_lead_state.md),
        so the first spelling that exists wins (brain's F18)."""
        spellings = [f"project_{role.replace('-', joint)}_state.md" for joint in ("-", "_", "")]
        folder = self.memory_folder(cwd)
        return next((name for name in spellings if folder and os.path.exists(os.path.join(folder, name))), spellings[0])

    def memory_folder(self, cwd: str) -> str:
        return os.path.join(self.transcripts, cwd.replace("/", "-").replace(".", "-"), "memory") if cwd else ""

    def modified_at(self, cwd: str, role: str) -> Optional[float]:
        if not cwd:
            return None
        try:
            return os.path.getmtime(os.path.join(self.memory_folder(cwd), self.state_file(role, cwd)))
        except OSError:
            return None

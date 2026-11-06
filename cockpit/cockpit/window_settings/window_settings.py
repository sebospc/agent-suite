from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple


class WindowSettings(ABC):
    """The settings files a session reads, read only. The auto-compact window Claude Code saved for one model in one account's user settings, read only: the first proof
    of the autopilot's /autocompact step (the owner, 2026-10-16)."""

    @abstractmethod
    def window(self, account: str, model: str) -> Optional[int]:
        """modelSettings.<model>.autoCompactWindow, or None when that account has none saved; raises SourceUnavailable."""

    @abstractmethod
    def plugin_layers(self, account: str, cwd: str, settings_flag: str) -> List[Tuple[str, Dict[str, bool]]]:
        """enabledPlugins of each settings layer that exists, lowest first: user (the account's), project, local, the
        --settings file; raises SourceUnavailable."""

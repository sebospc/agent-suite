from typing import Dict, List, Optional

from cockpit.hooks.hook_settings import HookSettings


class FakeHookSettings(HookSettings):
    def __init__(self, found: List[dict], logs: Optional[Dict[str, dict]] = None):
        self.found = found
        self.logs = logs or {}

    def hooks(self) -> List[dict]:
        return list(self.found)

    def log_activity(self, path: str, since: float) -> Optional[dict]:
        return self.logs.get(path)

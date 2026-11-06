import json
import os
from typing import List, Optional

from cockpit.hooks.hook_settings import HookSettings
from cockpit.source_unavailable import SourceUnavailable
from cockpit.times import parse_time


class SettingsFiles(HookSettings):
    """Claude Code settings.json files: {"hooks": {"<Event>": [{"matcher": ..., "hooks": [{"command": ...}]}]}}."""

    def __init__(self, paths: List[str]):
        self.paths = [os.path.expanduser(p) for p in paths]

    def hooks(self) -> List[dict]:
        found = []
        for path in self.paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    settings = json.load(handle)
            except (OSError, ValueError) as error:
                raise SourceUnavailable(f"{path}: {error}")
            for event, groups in (settings.get("hooks") or {}).items():
                for group in groups or []:
                    for hook in group.get("hooks") or []:
                        found.append({"source": path, "event": event, "matcher": group.get("matcher") or "",
                                      "command": hook.get("command") or hook.get("type") or ""})
        return found

    def log_activity(self, path: str, since: float) -> Optional[dict]:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return None
        today = 0
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                    stamp = entry.get("t") or entry.get("time")  # pause_guard.py writes "time" (brain's F21)
                except (ValueError, AttributeError):
                    continue
                stamp = stamp if isinstance(stamp, (int, float)) else parse_time(stamp)
                today += bool(stamp and stamp >= since)
        return {"last": os.path.getmtime(path), "today": today}

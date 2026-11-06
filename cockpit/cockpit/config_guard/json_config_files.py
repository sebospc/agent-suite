import glob
import json
import os
import time
from typing import List, Optional

from cockpit.config_guard.config_files import ConfigFiles
from cockpit.source_unavailable import SourceUnavailable

WATCHED = ("hooks", "enabledPlugins", "extraKnownMarketplaces", "mcpServers", "enabledMcpjsonServers", "statusLine")
SECRET_KEYS = ("env", "headers")  # an MCP server's env or headers can hold a token: never read into the baseline


def watched_part(settings: dict) -> dict:
    part = {key: settings[key] for key in WATCHED if key in settings}
    if isinstance(part.get("mcpServers"), dict):
        part["mcpServers"] = {name: {k: v for k, v in server.items() if k not in SECRET_KEYS} if isinstance(server, dict) else server
                              for name, server in part["mcpServers"].items()}
    return part


class JsonConfigFiles(ConfigFiles):
    def __init__(self, patterns: List[str], baseline_path: str):
        self.patterns = [os.path.expanduser(p) for p in patterns]
        self.baseline_path = os.path.expanduser(baseline_path)

    def read(self) -> dict:
        current = {path: self.part_of(path) for pattern in self.patterns
                   for path in (sorted(glob.glob(pattern)) if glob.has_magic(pattern) else [pattern])}
        try:
            with open(self.baseline_path, encoding="utf-8") as handle:
                saved = json.load(handle)
        except FileNotFoundError:
            saved = {"since": time.time(), "files": current}
            with open(self.baseline_path, "w", encoding="utf-8") as handle:
                json.dump(saved, handle, indent=1)
        except (OSError, ValueError) as error:
            raise SourceUnavailable(f"{self.baseline_path}: {error}")
        return {"current": current, "baseline": saved["files"], "since": saved["since"]}

    @staticmethod
    def part_of(path: str) -> Optional[dict]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                return watched_part(json.load(handle))
        except (OSError, ValueError) as error:
            return {"unreadable": str(error)}

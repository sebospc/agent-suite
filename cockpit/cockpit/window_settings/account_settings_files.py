import glob
import json
import os
from typing import Dict, List, Optional, Tuple

from cockpit.source_unavailable import SourceUnavailable
from cockpit.window_settings.window_settings import WindowSettings

DEFAULT_ACCOUNT = "default"


class AccountSettingsFiles(WindowSettings):
    """Each cswap account is its own CLAUDE_CONFIG_DIR, `<profiles>/<n>-<email>/`, with its own settings.json; the
    default login's is under ~/.claude."""

    def __init__(self, profiles_dir: str, default_settings: str):
        self.profiles_dir = os.path.expanduser(profiles_dir)
        self.default_settings = os.path.expanduser(default_settings)

    def window(self, account: str, model: str) -> Optional[int]:
        path = self.path_of(account)
        if not path or not os.path.exists(path):
            return None
        saved = ((read(path).get("modelSettings") or {}).get(model) or {}).get("autoCompactWindow")
        return saved if isinstance(saved, int) else None

    def plugin_layers(self, account: str, cwd: str, settings_flag: str) -> List[Tuple[str, Dict[str, bool]]]:
        paths = [("user", self.path_of(account))]
        if cwd:
            paths += [("project", os.path.join(cwd, ".claude", "settings.json")), ("local", os.path.join(cwd, ".claude", "settings.local.json"))]
        if settings_flag:
            paths.append(("--settings", os.path.expanduser(settings_flag)))
        return [(layer, read(path).get("enabledPlugins") or {}) for layer, path in paths if path and os.path.exists(path)]

    def path_of(self, account: str) -> str:
        if account == DEFAULT_ACCOUNT:
            return self.default_settings
        found = sorted(glob.glob(os.path.join(glob.escape(self.profiles_dir), f"{glob.escape(account)}-*", "settings.json")))
        return found[0] if account and found else ""


def read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise SourceUnavailable(f"{path}: {error}")

"""The project's team config, `.agent-suite.json` in the project folder.

Found through AGENT_SUITE_CONFIG, else $CLAUDE_PROJECT_DIR (set in every hook), else the current folder and its
parents. A missing file gives the defaults, so a tool still runs on a machine that has not adopted the suite.
"""
import json
import os
from pathlib import Path
from typing import Optional

FILE_NAME = ".agent-suite.json"
DEFAULTS = {
    "board_dir": "~/.agent-board",
    "session_prefix": "agent-",
    "lead": "lead",
    "coordinator": "coordinator",
    "team_json": "team.json",
    "slots": {},
    "courier": {"idle_minutes": 10, "cooldown_minutes": 30, "always_watched": ["coordinator"]},
    "team_check": {"stale_hours": 3},
    "snapshot": {},
    "parts": {},
}


class ConfigError(Exception):
    pass


def find(start: Optional[str] = None) -> Optional[Path]:
    explicit = os.environ.get("AGENT_SUITE_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    folder = Path(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).expanduser().resolve()
    for candidate in (folder, *folder.parents):
        if (candidate / FILE_NAME).is_file():
            return candidate / FILE_NAME
    return None


def load(start: Optional[str] = None) -> dict:
    path = find(start)
    raw = {}
    if path is not None and path.is_file():
        try:
            raw = json.loads(path.read_text())
        except ValueError as error:
            raise ConfigError(f"{path}: not readable JSON: {error}")
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: must hold one JSON object")
    unknown = sorted(set(raw) - set(DEFAULTS) - {"_note"})
    if unknown:
        raise ConfigError(f"{path}: unknown keys {', '.join(unknown)}")
    merged = {**DEFAULTS, **raw}
    for key in ("courier", "team_check"):
        merged[key] = {**DEFAULTS[key], **raw.get(key, {})}
    return merged


def board_path(config: dict, name: str) -> Path:
    # An absolute or ~ path in the config stays as it is; a bare name lives in the board folder.
    value = Path(os.path.expanduser(name))
    return value if value.is_absolute() else Path(os.path.expanduser(config["board_dir"])) / value


def session_name(config: dict, role: str) -> str:
    prefix = config["session_prefix"]
    return role if role.startswith(prefix) else prefix + role

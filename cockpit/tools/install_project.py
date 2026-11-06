# python3 tools/install_project.py install|uninstall DIR: wraps the cockpit's status line and pause guard into DIR's
# .claude/settings.json after a backup (a second install changes nothing); uninstall puts the original back, byte for byte.
import argparse
import json
import os
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cockpit.install.claude_settings import cockpit_commands, is_installed, with_cockpit, without_cockpit  # noqa: E402
from cockpit.project_config.config_error import ConfigError  # noqa: E402
from cockpit.project_config.project_config import load_config  # noqa: E402

BIN = os.path.join(ROOT, "bin")
BACKUP_SUFFIX = ".cockpit-backup"


def settings_path(project_dir: str) -> str:
    return os.path.join(os.path.expanduser(project_dir), ".claude", "settings.json")


def read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def parsed(raw: Optional[bytes], path: str) -> dict:
    if raw is None:
        return {}
    try:
        settings = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise ConfigError(f"{path}: not readable JSON, left as it is: {error}")
    if not isinstance(settings, dict):
        raise ConfigError(f"{path}: must hold one JSON object, left as it is")
    return settings


def write(path: str, content: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as handle:
        handle.write(content)
    os.replace(path + ".tmp", path)


def as_bytes(settings: dict) -> bytes:
    return (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def user_status_command() -> Optional[str]:
    # A project's statusLine hides the user's one, so the wrapper runs the user's line when the project has none.
    user_settings = os.path.expanduser("~/.claude/settings.json")
    return (parsed(read_bytes(user_settings), user_settings).get("statusLine") or {}).get("command")


def install(project_dir: str) -> str:
    paths = load_config(project_dir)["paths"]
    path = settings_path(project_dir)
    raw = read_bytes(path)
    settings = parsed(raw, path)
    if is_installed(settings, BIN):
        return f"already installed in {path}; nothing changed"
    if os.path.exists(path + BACKUP_SUFFIX):
        raise ConfigError(f"{path + BACKUP_SUFFIX} is left from an earlier install; check it and remove it first")
    if raw is not None:
        write(path + BACKUP_SUFFIX, raw)
    original_status = (settings.get("statusLine") or {}).get("command") or user_status_command()
    commands = cockpit_commands(BIN, paths["usage"], paths["pause_file"], original_status)
    write(path, as_bytes(with_cockpit(settings, commands)))
    return f"installed in {path}" + (f"; backup at {path + BACKUP_SUFFIX}" if raw is not None else "")


def uninstall(project_dir: str) -> str:
    path = settings_path(project_dir)
    backup_path = path + BACKUP_SUFFIX
    settings = parsed(read_bytes(path), path)
    if not is_installed(settings, BIN):
        return f"not installed in {path}; nothing changed"
    backup = read_bytes(backup_path)
    original = parsed(backup, backup_path)
    stripped = without_cockpit(settings, BIN, original)
    if backup is not None and stripped == original:
        write(path, backup)
        os.remove(backup_path)
        return f"uninstalled: {path} is back to its original"
    if backup is None and not stripped:
        os.remove(path)
        return f"uninstalled: {path} did not exist before, so it is gone again"
    # The project changed its settings after the install: keep those changes and the backup to compare.
    write(path, as_bytes(stripped))
    return f"uninstalled the cockpit's entries; {path} changed since the install" + (
        f", so the backup stays at {backup_path}" if backup is not None else "")


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Install or remove the cockpit's status line and pause guard in a project.")
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("project_dir")
    args = parser.parse_args(argv)
    try:
        print(install(args.project_dir) if args.action == "install" else uninstall(args.project_dir))
    except ConfigError as error:
        print(f"install_project: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

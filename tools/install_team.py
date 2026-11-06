#!/usr/bin/env python3
"""python3 tools/install_team.py install|uninstall|status DIR

Wraps the hooks of the parts DIR chose (DIR/.agent-suite.json, parts: name -> as-is | adapted | skip) into
DIR/.claude/settings.json, after a backup. A second install with the same choices changes nothing; a changed choice
swaps only the suite's own entries. Uninstall puts the original back byte for byte; if the project changed its
settings after the install, only the suite's entries go and the backup stays to compare.

The suite's entries are the commands that run a script under this folder's tools/team/, so an entry the project
wrote itself is never touched.
"""
import copy
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Optional

SUITE = Path(__file__).resolve().parent.parent
TEAM = SUITE / "tools" / "team"
BACKUP_SUFFIX = ".agent-suite-backup"
CHOSEN = ("as-is", "adapted")


class InstallError(Exception):
    pass


def manifest() -> dict:
    return json.loads((SUITE / "parts.json").read_text())["parts"]


def choices(project_dir: Path) -> dict:
    path = project_dir / ".agent-suite.json"
    try:
        parts = json.loads(path.read_text()).get("parts", {})
    except FileNotFoundError:
        raise InstallError(f"{path} is missing: write the project config first (the adopt skill does)")
    except ValueError as error:
        raise InstallError(f"{path}: not readable JSON: {error}")
    known = manifest()
    unknown = sorted(set(parts) - set(known))
    if unknown:
        raise InstallError(f"{path}: unknown parts {', '.join(unknown)}")
    wrong = sorted(name for name, choice in parts.items() if choice not in (*CHOSEN, "skip"))
    if wrong:
        raise InstallError(f"{path}: each part is as-is, adapted or skip; not: {', '.join(wrong)}")
    return parts


def wanted_hooks(parts: dict) -> list:
    """(event, matcher, command) for every hook of a chosen part, in manifest order, each command once."""
    chosen = {name for name, choice in parts.items() if choice in CHOSEN}
    hooks = []
    for name, part in manifest().items():
        if name not in chosen:
            continue
        for hook in part["hooks"]:
            if hook.get("skip_with") in chosen:
                continue
            command = shlex.join(["python3", str(TEAM / hook["script"]), *hook.get("args", [])])
            entry = (hook["event"], hook["matcher"], command)
            if entry not in hooks:
                hooks.append(entry)
    return hooks


def is_ours(command: str) -> bool:
    return f"{TEAM}/" in (command or "")


def our_hooks(settings: dict) -> list:
    return [(event, group.get("matcher", ""), hook.get("command", ""))
            for event, groups in (settings.get("hooks") or {}).items() for group in groups
            for hook in group.get("hooks") or [] if is_ours(hook.get("command", ""))]


def without_ours(settings: dict, original: dict) -> dict:
    stripped = copy.deepcopy(settings)
    hooks = stripped.get("hooks")
    if not isinstance(hooks, dict):
        return stripped
    for event in list(hooks):
        kept = [group for group in hooks[event]
                if not any(is_ours(hook.get("command", "")) for hook in group.get("hooks") or [])]
        if kept or event in (original.get("hooks") or {}):
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks and "hooks" not in original:
        del stripped["hooks"]
    return stripped


def with_hooks(settings: dict, hooks: list) -> dict:
    installed = copy.deepcopy(settings)
    groups = installed.setdefault("hooks", {})
    for event, matcher, command in hooks:
        group = {"hooks": [{"type": "command", "command": command}]}
        groups.setdefault(event, []).append({"matcher": matcher, **group} if matcher else group)
    return installed


def read_bytes(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def parsed(raw: Optional[bytes], path: Path) -> dict:
    if raw is None:
        return {}
    try:
        settings = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise InstallError(f"{path}: not readable JSON, left as it is: {error}")
    if not isinstance(settings, dict):
        raise InstallError(f"{path}: must hold one JSON object, left as it is")
    return settings


def write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def as_bytes(settings: dict) -> bytes:
    return (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def install(project_dir: Path) -> str:
    hooks = wanted_hooks(choices(project_dir))
    path = project_dir / ".claude" / "settings.json"
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    raw = read_bytes(path)
    settings = parsed(raw, path)
    if sorted(our_hooks(settings)) == sorted(hooks):
        return f"already installed in {path}; nothing changed"
    if not our_hooks(settings):
        if backup.exists():
            raise InstallError(f"{backup} is left from an earlier install; check it and remove it first")
        if raw is not None:
            write(backup, raw)
    original = parsed(read_bytes(backup), backup)
    write(path, as_bytes(with_hooks(without_ours(settings, original), hooks)))
    return f"installed {len(hooks)} hooks in {path}" + (f"; backup at {backup}" if backup.exists() else "")


def uninstall(project_dir: Path) -> str:
    path = project_dir / ".claude" / "settings.json"
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    settings = parsed(read_bytes(path), path)
    if not our_hooks(settings):
        return f"not installed in {path}; nothing changed"
    backup_raw = read_bytes(backup)
    original = parsed(backup_raw, backup)
    stripped = without_ours(settings, original)
    if backup_raw is not None and stripped == original:
        write(path, backup_raw)
        backup.unlink()
        return f"uninstalled: {path} is back to its original"
    if backup_raw is None and not stripped:
        path.unlink()
        return f"uninstalled: {path} did not exist before, so it is gone again"
    write(path, as_bytes(stripped))
    return f"uninstalled the suite's hooks; {path} changed since the install" + (
        f", so the backup stays at {backup}" if backup_raw is not None else "")


def status(project_dir: Path) -> str:
    settings = parsed(read_bytes(project_dir / ".claude" / "settings.json"), project_dir)
    have, want = set(our_hooks(settings)), set(wanted_hooks(choices(project_dir)))
    lines = [f"missing: {event} {matcher} {command}" for event, matcher, command in sorted(want - have)]
    lines += [f"not chosen: {event} {matcher} {command}" for event, matcher, command in sorted(have - want)]
    return "\n".join(lines) or f"installed: {len(have)} hooks, as chosen"


def main(argv) -> int:
    if len(argv) != 2 or argv[0] not in ("install", "uninstall", "status"):
        print(__doc__, file=sys.stderr)
        return 2
    project_dir = Path(argv[1]).expanduser().resolve()
    try:
        print({"install": install, "uninstall": uninstall, "status": status}[argv[0]](project_dir))
    except InstallError as error:
        print(f"install_team: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

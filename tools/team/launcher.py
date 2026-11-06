#!/usr/bin/env python3
"""The launcher parts of the claude wrapper (templates/shell/): session name from the pane label, saved flags.

  launcher.py args [ARG ...]   prints the session name, then the arguments to run claude with, NUL-separated
  launcher.py session-start    SessionStart hook: saves the session's flags for its next bare resume
  launcher.py forget           the wrapper's cleanup after claude exits

- herdr restores a pane as a bare `claude --resume <id>`; the session gets back the flags it was started with.
- In a herdr pane labelled with a team role (with or without the session prefix), a launch with no --name gets
  `--name <prefix><role>`, so the cockpit and the guards find the session; a fresh launch with no flags of its own
  also gets the role's `launch` flags from team.json.
State: <board>/launcher/ (args per wrapper pid, flags per session id).
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import suite_config  # noqa: E402

RESUME = ("--resume", "-r")
NAME = ("--name", "-n")


def state_dir(config: dict) -> Path:
    return suite_config.board_path(config, "launcher")


def pane_label() -> str:
    out = subprocess.run(["herdr", "pane", "current"], capture_output=True, text=True).stdout
    try:
        return json.loads(out)["result"]["pane"].get("label") or ""
    except (ValueError, KeyError, TypeError):
        return ""


def team(config: dict) -> dict:
    try:
        sessions = json.loads(suite_config.board_path(config, config["team_json"]).read_text()).get("sessions", {})
    except (OSError, ValueError):
        return {}
    prefix = config["session_prefix"]
    return {name[len(prefix):] if name.startswith(prefix) else name: plan for name, plan in sessions.items()}


def bare_resume(args: list) -> Optional[str]:
    return args[1] if len(args) == 2 and args[0] in RESUME else None


def name_in(args: list) -> str:
    for index, arg in enumerate(args):
        if arg in NAME and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--name="):
            return arg.split("=", 1)[1]
    return ""


def with_launch_flags(args: list, config: dict, label: str, saved: dict) -> list:
    resumed = bare_resume(args)
    if resumed and resumed in saved:
        args = [*saved[resumed], *args]
    if label and not name_in(args):
        prefix = config["session_prefix"]
        role = label[len(prefix):] if label.startswith(prefix) else label
        roles = team(config)
        if role in roles:
            if not args:
                args = list(roles[role].get("launch", []))
            args = [*args, "--name", prefix + role]
    return args


def saved_flags(config: dict) -> dict:
    folder = state_dir(config) / "flags"
    return {path.stem: json.loads(path.read_text()) for path in folder.glob("*.json")} if folder.is_dir() else {}


def without_resume(args: list) -> list:
    kept, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in RESUME:
            skip = True
        elif not arg.startswith("--resume="):
            kept.append(arg)
    return kept


def main(argv) -> int:
    config = suite_config.load()
    if argv[:1] == ["args"]:
        label = pane_label() if os.environ.get("HERDR_PANE_ID") else ""
        args = with_launch_flags(argv[1:], config, label, saved_flags(config))
        wrapper = os.environ.get("CLAUDE_WRAPPER_PID")
        if wrapper:
            (state_dir(config) / "args").mkdir(parents=True, exist_ok=True)
            (state_dir(config) / "args" / wrapper).write_text("\0".join(args))
        sys.stdout.write("\0".join([name_in(args), *args]))
        return 0
    if argv[:1] == ["session-start"]:
        try:
            session_id = json.load(sys.stdin).get("session_id", "")
            wrapper = os.environ.get("CLAUDE_WRAPPER_PID", "")
            raw = (state_dir(config) / "args" / wrapper).read_text() if wrapper else ""
        except (OSError, ValueError):
            return 0
        flags = without_resume([arg for arg in raw.split("\0") if arg])
        if session_id and flags:
            (state_dir(config) / "flags").mkdir(parents=True, exist_ok=True)
            (state_dir(config) / "flags" / f"{session_id}.json").write_text(json.dumps(flags))
        return 0
    if argv[:1] == ["forget"]:
        (state_dir(config) / "args" / os.environ.get("CLAUDE_WRAPPER_PID", "none")).unlink(missing_ok=True)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

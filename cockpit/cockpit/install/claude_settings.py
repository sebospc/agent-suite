import copy
import shlex
from typing import Optional

# Agent Deck's way: the cockpit's entries are recognised by the path of its own scripts, so install and uninstall
# never touch an entry the project wrote itself.
GUARDED_TOOL = "Bash"


def cockpit_commands(bin_dir: str, usage_path: str, pause_file: str, original_status: Optional[str]) -> dict:
    status = ["python3", f"{bin_dir}/statusline.py", usage_path] + ([original_status] if original_status else [])
    return {"status": shlex.join(status), "guard": shlex.join(["python3", f"{bin_dir}/pause_guard.py", pause_file])}


def is_ours(command: str, bin_dir: str) -> bool:
    return f"{bin_dir}/" in (command or "")


def is_installed(settings: dict, bin_dir: str) -> bool:
    return is_ours((settings.get("statusLine") or {}).get("command", ""), bin_dir) or any(
        is_ours(hook.get("command", ""), bin_dir) for groups in (settings.get("hooks") or {}).values()
        for group in groups for hook in group.get("hooks") or [])


def with_cockpit(settings: dict, commands: dict) -> dict:
    installed = copy.deepcopy(settings)
    # The project's own status line keeps its padding and type; the wrapper runs its command after saving the limits.
    installed["statusLine"] = dict(installed.get("statusLine") or {"type": "command"}, command=commands["status"])
    hooks = installed.setdefault("hooks", {})
    hooks.setdefault("PreToolUse", []).append({"matcher": GUARDED_TOOL, "hooks": [{"type": "command", "command": commands["guard"]}]})
    return installed


def without_cockpit(settings: dict, bin_dir: str, original: dict) -> dict:
    stripped = copy.deepcopy(settings)
    if is_ours((stripped.get("statusLine") or {}).get("command", ""), bin_dir):
        if "statusLine" in original:
            stripped["statusLine"] = original["statusLine"]
        else:
            del stripped["statusLine"]
    hooks = stripped.get("hooks")
    if isinstance(hooks, dict):
        for event in list(hooks):
            kept = [group for group in hooks[event]
                    if not any(is_ours(hook.get("command", ""), bin_dir) for hook in group.get("hooks") or [])]
            if kept or event in (original.get("hooks") or {}):
                hooks[event] = kept
            else:
                del hooks[event]
        if not hooks and "hooks" not in original:
            del stripped["hooks"]
    return stripped

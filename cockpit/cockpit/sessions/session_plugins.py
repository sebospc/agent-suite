import os
from typing import Dict, List, Sequence, Tuple


def enabled_plugins(layers: List[Tuple[str, Dict[str, bool]]], flags: Sequence[str]) -> List[str]:
    """What a session really loads: a later layer wins over an earlier one (user, project, local, --settings), and each
    --plugin-dir adds its folder's plugin. "caveman@caveman" shows as caveman."""
    merged: Dict[str, bool] = {}
    for _, enabled in layers:
        merged.update(enabled)
    names = {plugin.split("@")[0] for plugin, on in merged.items() if on is True}
    names |= {os.path.basename(value.rstrip("/")) for flag, value in zip(flags, flags[1:]) if flag == "--plugin-dir"}
    return sorted(names)


def settings_flag(flags: Sequence[str]) -> str:
    return next((value for flag, value in zip(flags, flags[1:]) if flag == "--settings"), "")


# A start mode's name as its plugin's (brain runs i-have-adhd as its own SessionStart hook, not as a plugin).
MODE_PLUGIN = {"adhd": "i-have-adhd"}


def hook_plugins(start_modes: Sequence[str], plugins: Sequence[str]) -> List[str]:
    """Modes its last start's SessionStart hooks switched on that no loaded plugin explains (pg-g22n)."""
    return sorted({MODE_PLUGIN.get(mode, mode) for mode in start_modes} - set(plugins))

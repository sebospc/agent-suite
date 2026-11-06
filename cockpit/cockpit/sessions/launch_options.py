import os
from typing import List, Sequence, Tuple

# Claude Code flags that take a value; any other flag stands alone, and a word that is no flag is the prompt.
VALUE_FLAGS = {"--settings", "--plugin-dir", "--name", "--model", "--effort", "--resume", "--session-id", "--permission-mode",
               "--add-dir", "--mcp-config", "--append-system-prompt", "--system-prompt", "--agent", "--fallback-model"}
SHORT = {"-n": "--name", "-r": "--resume"}


def options(flags: Sequence[str]) -> List[Tuple[str, str]]:
    """A command line's flags as (flag, value) pairs, "" for a flag without one; --x=v and -n are spelled out."""
    found, i = [], 0
    while i < len(flags):
        flag, value = flags[i], ""
        if flag.startswith("--") and "=" in flag:
            flag, value = flag.split("=", 1)
        flag = SHORT.get(flag, flag)
        if flag in VALUE_FLAGS and not value and i + 1 < len(flags):
            value, i = flags[i + 1], i + 1
        if flag.startswith("-"):
            found.append((flag, os.path.expanduser(value)))
        i += 1
    return found


def flat(pairs: Sequence[Tuple[str, str]]) -> List[str]:
    return [part for flag, value in pairs for part in ((flag, value) if value else (flag,))]

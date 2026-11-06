import os
import re
from typing import Dict, List

from cockpit.display_time import when
from cockpit.hooks.hook_settings import HookSettings

SCRIPT = re.compile(r"[\w./~$-]+\.(?:py|sh|mjs|js)\b")


def script_name(command: str) -> str:
    """The script a hook runs, not its last shell word: commands end in fi, a quote or an argument (brain's report F3)."""
    found = SCRIPT.findall(command)
    if found:
        return os.path.basename(found[0])
    words = command.replace('"', " ").replace("'", " ").split()
    return os.path.basename(words[0]) if words else command


def hooks_view(settings: HookSettings, logs: Dict[str, str], since: float, now: float) -> List[dict]:
    """One line per script, with every event it runs on (brain's pg-wk0s: claude-hook.sh was listed 10 times), and what
    its log says it did today. logs maps a word in the hook's command (its script's name) to the log it writes
    (.cockpit.json paths.hook_logs)."""
    by_script: Dict[str, dict] = {}
    for hook in settings.hooks():
        script = script_name(hook["command"])
        shown = by_script.setdefault(script, {"script": script, "events": [], "commands": [], "sources": []})
        event = hook["event"] + (f" ({hook['matcher']})" if hook["matcher"] else "")
        for key, value in (("events", event), ("commands", hook["command"]), ("sources", hook["source"])):
            if value not in shown[key]:
                shown[key].append(value)
    for shown in by_script.values():
        log_path = next((path for word, path in logs.items() if any(word in c for c in shown["commands"])), "")
        activity = settings.log_activity(log_path, since) if log_path else None
        shown["log"] = log_path
        shown["did"] = (f"{activity['today']} today, last {when(activity['last'], now)}" if activity
                        else "writes no log the cockpit reads")
    return list(by_script.values())

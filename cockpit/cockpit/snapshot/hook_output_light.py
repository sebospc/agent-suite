from typing import Dict

from cockpit.display_time import clock_time
from cockpit.hooks.hooks_view import SCRIPT, script_name
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light

# Claude Code keeps a hook's output for the model only up to this; past it the model gets a 2k stub and a file path.
HOOK_OUTPUT_LIMIT = 10_000
RULE = f"ACT when a hook's last output is {HOOK_OUTPUT_LIMIT:,} characters or more: the model saw only a stub of it"
SOURCE = "transcripts: each hook command's last hook_success stdout, in the running sessions (measured)"


def hook_output_light(named: Dict[str, object]) -> dict:
    """Each hook script's last output across the running sessions, its biggest one first (calibration step 5)."""
    last: Dict[str, tuple] = {}  # script -> (time, characters, session) of its newest output
    for name, stats in named.items():
        for command, at, chars in getattr(stats, "hook_outputs", ()):
            script = script_name(command) if SCRIPT.search(command) else command  # caveman's is "Loading caveman mode..."
            if script not in last or at > last[script][0]:
                last[script] = (at, chars, name)
    rows = sorted(({"id": script, "script": script, "chars": chars, "session": session, "at": clock_time(at) if at else ""}
                   for script, (at, chars, session) in last.items()), key=lambda r: -r["chars"])
    over = [r["script"] for r in rows if r["chars"] >= HOOK_OUTPUT_LIMIT]
    value = f"{len(over)} over 10k" if over else f"largest {rows[0]['chars']:,} chars" if rows else "no run read"
    why = (f"{', '.join(over)}: the last output passed {HOOK_OUTPUT_LIMIT:,} characters, so the model got a stub" if over
           else f"Every hook's last output is under {HOOK_OUTPUT_LIMIT:,} characters" if rows else "No hook output in the running sessions' transcripts")
    columns = [("script", "Hook", "text"), ("chars", "Last output, chars", "count"), ("session", "Session", "text"), ("at", "At", "text")]
    return light("hook_output", "Hook output", value, "act" if over else "ok", "", why + ".", RULE, SOURCE,
                 table(f"Each hook's last output; Claude Code keeps {HOOK_OUTPUT_LIMIT:,} characters", columns, rows))

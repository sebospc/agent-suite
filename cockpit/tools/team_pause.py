"""One switch for the team's pause, shared by brain and the cockpit (the owner, 2026-10-16: "un solo switch disponible
para brain y cockpit, idealmente programatico"). brain runs it when the owner says off or on; the cockpit's button
writes the same file; brain's hook blocks commits, pushes and bead claims while it exists.

    python3 tools/team_pause.py off      # pause the team
    python3 tools/team_pause.py on       # resume it
    python3 tools/team_pause.py status   # paused since <time>, or running
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cockpit.pause.pause_file import PauseFile  # noqa: E402  (the same adapter the cockpit uses)
from cockpit.project_config.project_config import load_config  # noqa: E402


def main(argv) -> int:
    if len(argv) != 2 or argv[1] not in ("off", "on", "status"):
        print("usage: team_pause.py off|on|status", file=sys.stderr)
        return 2
    switch = PauseFile(load_config(ROOT)["paths"]["pause_file"])
    if argv[1] != "status":
        switch.set(argv[1] == "off", time.time())
    since = switch.since()
    print(f"paused since {time.strftime('%Y-%m-%d %H:%M', time.localtime(since))}" if since else "running")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

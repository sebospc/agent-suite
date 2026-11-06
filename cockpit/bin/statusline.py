# Status line wrapper (tools/install_project.py): saves the plan limits Claude Code reports, for the Accounts view,
# then prints the project's own status line, so the person sees the line they had.
import json
import os
import subprocess
import sys
import time


def save_limits(raw: str, usage_path: str) -> None:
    try:
        limits = json.loads(raw).get("rate_limits")
    except (ValueError, AttributeError):
        return
    if limits is None:
        return
    os.makedirs(os.path.dirname(usage_path) or ".", exist_ok=True)
    with open(usage_path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump({"rate_limits": limits, "at": time.time()}, handle)
    os.replace(usage_path + ".tmp", usage_path)  # the cockpit never reads a half-written file


def main(argv) -> int:
    raw = sys.stdin.read()
    save_limits(raw, os.path.expanduser(argv[1]))
    if len(argv) > 2:
        shown = subprocess.run(argv[2], shell=True, input=raw, capture_output=True, text=True)
        sys.stdout.write(shown.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

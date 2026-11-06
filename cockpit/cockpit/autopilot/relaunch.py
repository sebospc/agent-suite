import os
import shlex
from typing import List, Optional

from cockpit.sessions.launch_options import flat, options
from cockpit.team import session_name

# A relaunch keeps what the session runs with and team.json does not name: the balancer's resume carries --model.
CARRIED = ("--model", "--effort")
EXIT_WAIT_S = 5 * 60  # a session still running this long after its /exit did not exit; the relaunch is dropped
# What every team session starts with when its team.json entry lists no launch flags (brain, pg-o1sq relaunch HOLD):
# a resume that carries any flag gets none of its saved ones, so a relaunch names them all.
DEFAULT_LAUNCH = ["--dangerously-skip-permissions"]


def team_flags(row: dict) -> List[str]:
    """team.json's launch flags, or the default; with --name <prefix><role>, which the cockpit finds each session by."""
    flags = list(row.get("launch") or DEFAULT_LAUNCH)
    named = {flag for flag, _ in options(flags)}
    if row.get("name") and "--name" not in named:
        flags += ["--name", session_name(row['name'])]
    return flags + flat([(f, v) for f, v in options(row.get("flags") or []) if f in CARRIED and f not in named])


def relaunch_command(row: dict, flags: Optional[List[str]] = None) -> str:
    """Typed into its pane's shell once it exited: the same session resumed, through the claude wrapper (account and
    name), with every team.json flag. A launch that carries flags gets none of its saved ones, so team.json lists them all.
    Q_TERM=1 keeps Kiro's terminal wrapper off, so herdr sees the agent again."""
    flags = [os.path.expanduser(f) for f in (team_flags(row) if flags is None else flags)]
    return " ".join(["Q_TERM=1", "claude", "--resume", row["session_id"]] + [shlex.quote(f) for f in flags])

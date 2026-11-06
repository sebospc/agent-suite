import json
import os
import subprocess
from typing import Callable, List

from cockpit.board.bead import Bead
from cockpit.board.board import Board
from cockpit.board.board_state import BoardState
from cockpit.milestone.milestone_plan import MilestonePlan
from cockpit.source_unavailable import SourceUnavailable


class BdBoard(Board):
    """Reads beads with one `bd export --all` (dependencies and comments in one consistent read)."""

    def __init__(self, folder: str, command: List[str], timeout_s: float, now: Callable[[], float], milestone_plan: MilestonePlan):
        self.folder = os.path.expanduser(folder)
        self.command = command
        self.timeout_s = timeout_s
        self.now = now
        self.milestone_plan = milestone_plan

    def read(self) -> BoardState:
        read_at = self.now()
        try:
            # bd waits on the board lock while a session writes; past the timeout this read fails, never hangs.
            done = subprocess.run(self.command, cwd=self.folder, capture_output=True, text=True, timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            raise SourceUnavailable(f"{' '.join(self.command)} took over {self.timeout_s:g} s (board locked?)")
        except OSError as error:
            raise SourceUnavailable(f"{' '.join(self.command)}: {error}")
        beads = parse_beads(done.stdout)
        if not beads:
            raise SourceUnavailable(f"{' '.join(self.command)} returned no beads (exit {done.returncode})")
        plan = self.milestone_plan.read()
        return BoardState(beads=beads, dod=plan.dod if plan else {}, goal=plan.goal if plan else {},
                          goal_read_at=plan.goal_read_at if plan else 0.0, read_at=read_at,
                          source=f"{' '.join(self.command)} in {self.folder}", milestone_used=plan is not None)


def parse_beads(text: str) -> List[Bead]:
    beads = []
    for line in text.splitlines():
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if isinstance(raw, dict) and str(raw.get("id", "")).startswith(("mb-", "pg-")):
            beads.append(Bead.from_export(raw))
    return beads


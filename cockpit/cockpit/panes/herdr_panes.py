import json
import os
import subprocess
from typing import Dict, List

from cockpit.panes.input_line import input_text
from cockpit.panes.panes import Panes
from cockpit.source_unavailable import SourceUnavailable


SCREEN_LINES = 40  # the input box sits in the last lines; a long unsent message can take a dozen


class HerdrPanes(Panes):
    def __init__(self, herdr: List[str], timeout_s: float):
        self.herdr = [os.path.expanduser(part) for part in herdr]
        self.timeout_s = timeout_s

    def type_into(self, pane: str, text: str) -> None:
        """Only into an empty input line: text the owner typed and did not send yet would merge with it (brain,
        pg-cpfu HOLD: two ANSWER notices merged into the owner's message). The caller holds it and tries again."""
        typed = input_text(self.herdr_call(["pane", "read", pane, "--source", "visible", "--lines", str(SCREEN_LINES), "--ansi"]))
        if typed is None:
            raise SourceUnavailable(f"herdr pane read {pane}: no input line on its screen, so nothing is typed")
        if typed:
            raise SourceUnavailable(f"its input line holds unsent text ({len(typed)} characters), so it waits")
        try:
            self.herdr_call(["agent", "prompt", pane, text])
        except SourceUnavailable as error:
            # herdr does not know every Claude pane as an agent (agent-ddp on w9:p1, 2026-10-23); typed in, the text still lands.
            if "agent_not_found" not in str(error):
                raise
            self.herdr_call(["pane", "send-text", pane, text])
            self.herdr_call(["pane", "send-keys", pane, "enter"])

    def notify(self, title: str, body: str) -> None:
        self.herdr_call(["notification", "show", title, "--body", body, "--sound", "request"])

    def run_in(self, pane: str, command: str) -> None:
        self.herdr_call(["pane", "run", pane, command])

    def labels(self) -> Dict[str, str]:
        try:
            panes = json.loads(self.herdr_call(["pane", "list"])).get("result", {}).get("panes", [])
        except ValueError as error:
            raise SourceUnavailable(f"herdr pane list: {error}")
        return {p["pane_id"]: p.get("label") or p.get("terminal_title_stripped") or "" for p in panes}

    def herdr_call(self, args: List[str]) -> str:
        name = " ".join(["herdr"] + args[:3])
        try:
            done = subprocess.run(self.herdr + args, capture_output=True, text=True, timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailable(f"{name}: {error}")
        if done.returncode != 0:
            raise SourceUnavailable(f"{name} exited {done.returncode}: {done.stderr.strip()[:200]}")
        return done.stdout

from typing import Dict, List

from cockpit.action_log.action_log import ActionLog
from cockpit.source_unavailable import SourceUnavailable

WINDOW_S = 2 * 7 * 86400  # the two weeks the fitters read


class SessionChanges:
    """Writes to actions.jsonl the changes no control of the cockpit made, so a fitter can tell a confounded decision
    (pg-6inz, brain): a session's process started again (a balancer move or a hand relaunch rewrites its cache and can
    change its flags), and Claude Code's own auto-compaction. Each is written once, by its own time."""

    def __init__(self, action_log: ActionLog, now: float):
        self.action_log = action_log
        self.started: Dict[str, float] = {}
        self.compacted: Dict[str, float] = {}
        try:
            for r in action_log.since(now - WINDOW_S):
                if r.get("event") == "process_started":
                    self.started[r["session"]] = max(self.started.get(r["session"], 0), r["at"])
                elif r.get("event") == "auto_compacted":
                    self.compacted[r["session"]] = max(self.compacted.get(r["session"], 0), r["at"])
        except SourceUnavailable:
            pass

    def step(self, rows: List[dict], now: float) -> None:
        for row in rows:
            started, compacted = row.get("process_started_at") or 0, row.get("last_auto_compaction_at") or 0
            if started > self.started.get(row["name"], 0):
                self.started[row["name"]] = started
                self.write({"t": now, "event": "process_started", "origin": "autopilot", "session": row["name"], "at": started})
            if compacted > self.compacted.get(row["name"], 0):
                self.compacted[row["name"]] = compacted
                self.write({"t": now, "event": "auto_compacted", "origin": "autopilot", "session": row["name"], "at": compacted})

    def write(self, record: dict) -> None:
        try:
            self.action_log.append(record)
        except SourceUnavailable:
            pass  # written on the next read

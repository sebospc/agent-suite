import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import task_queue
import team_check

CONFIG = {"team_check": {"stale_hours": 3}}
NOW = datetime(2026, 1, 2, 12, tzinfo=timezone.utc).timestamp()


def bead(id_, who, hours_ago=0):
    stamp = datetime.fromtimestamp(NOW - hours_ago * 3600, timezone.utc).isoformat()
    return {"id": id_, "assignee": who, "updated_at": stamp}


def board():
    return {"tasks": [], "waiting_owner": [], "queue": []}


class TeamCheckTest(unittest.TestCase):
    def check(self, in_progress=(), ready=(), b=None, closed=(), slot_board=None):
        return team_check.findings(CONFIG, ["agent-ios", "agent-ai"], list(in_progress), list(ready), b or board(),
                                   set(closed), slot_board or {}, NOW)

    def test_a_team_in_order_has_no_findings(self):
        self.assertEqual([], self.check(in_progress=[bead("t-1", "agent-ios", 1)], ready=[bead("t-2", "agent-ios")]))

    def test_two_in_progress_and_a_stale_one_are_found(self):
        lines = self.check(in_progress=[bead("t-1", "agent-ios", 1), bead("t-2", "agent-ios", 5)])
        self.assertEqual(["agent-ios: 2 beads in progress (t-1, t-2); one at a time",
                          "agent-ios: t-2 in progress, no update for 5 h"], lines)

    def test_idle_with_ready_work_unless_it_holds_a_task_in_flight(self):
        self.assertEqual(["agent-ai: ready beads but nothing in progress or in flight"],
                         self.check(ready=[bead("t-3", "agent-ai")]))
        b = board()
        task_queue.start(b, "t-4", ["agent-ai"])
        self.assertEqual([], self.check(ready=[bead("t-3", "agent-ai")], b=b))

    def test_a_closed_bead_in_flight_and_an_overdue_slot_are_found(self):
        b = board()
        task_queue.start(b, "t-4", ["agent-ai"])
        slot_board = {"test-db": {"holder": {"session": "agent-ai", "minutes": 10, "since": NOW - 3600}, "waiting": []}}
        self.assertEqual(["in flight: t-4 is closed; take it off (task_queue.py done)",
                          "slot test-db held by agent-ai for 60 min"],
                         self.check(b=b, closed=["t-4"], slot_board=slot_board))


if __name__ == "__main__":
    unittest.main()

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import task_queue as q


class TaskQueueTest(unittest.TestCase):
    def setUp(self):
        self.board = q.read(Path(tempfile.mkdtemp()) / "in_flight.json")

    def test_a_session_holds_one_ticket_and_disjoint_sessions_run_together(self):
        q.start(self.board, "t-1", ["agent-ios"])
        q.start(self.board, "t-2", ["agent-ai"])
        with self.assertRaisesRegex(q.Refused, "agent-ios already holds t-1"):
            q.start(self.board, "t-3", ["agent-ios", "agent-backend"])
        self.assertEqual("t-1", q.holder(self.board, "agent-ios"))

    def test_waiting_on_the_owner_frees_the_session(self):
        q.start(self.board, "t-1", ["agent-ios"])
        q.wait(self.board, "t-1", ask="a1b2c3")
        self.assertIsNone(q.holder(self.board, "agent-ios"))
        self.assertEqual("a1b2c3", self.board["waiting_owner"][0]["ask"])
        q.start(self.board, "t-2", ["agent-ios"])

    def test_hand_starts_the_next_queued_ticket_only_for_a_free_session(self):
        q.add(self.board, "agent-ios", ["t-1", "t-2"])
        self.assertEqual("t-1", q.hand(self.board, "agent-ios"))
        self.assertIsNone(q.hand(self.board, "agent-ios"))
        q.take(self.board, "t-1")
        self.assertEqual("t-2", q.hand(self.board, "agent-ios"))
        self.assertEqual([], self.board["queue"][0]["next"])

    def test_a_refused_change_writes_nothing(self):
        path = Path(tempfile.mkdtemp()) / "in_flight.json"
        with q.locked(path) as board:
            q.start(board, "t-1", ["agent-ios"])
        with self.assertRaises(q.Refused):
            with q.locked(path) as board:
                q.add(board, "agent-ios", ["t-9"])
                q.start(board, "t-2", ["agent-ios"])
        self.assertEqual([], q.read(path)["queue"])


if __name__ == "__main__":
    unittest.main()

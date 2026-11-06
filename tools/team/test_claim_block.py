import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claim_block
import task_queue


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class ClaimBlockTest(unittest.TestCase):
    def setUp(self):
        board_dir = tempfile.mkdtemp()
        self.config = {"board_dir": board_dir}
        self.path = Path(board_dir) / "in_flight.json"
        env = mock.patch.dict(os.environ, {"AGENT_IN_FLIGHT": str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("AGENT_SESSION", None)
        os.environ.pop("BEADS_ACTOR", None)

    def deny(self, command, in_progress=()):
        return claim_block.denial(bash(command), self.config, lambda session, board: list(in_progress))

    def test_a_second_in_progress_bead_blocks_the_claim(self):
        self.assertEqual("agent-ios already has t-1 in progress",
                         self.deny("cd ~/b && BEADS_ACTOR=agent-ios bd update t-2 --claim", ["t-1"]))
        self.assertIsNone(self.deny("BEADS_ACTOR=agent-ios bd update t-1 --claim", ["t-1"]))
        self.assertIsNotNone(self.deny("BEADS_ACTOR=agent-ios bd update t-2 --status in_progress", ["t-1"]))
        self.assertIsNotNone(self.deny("BEADS_ACTOR=agent-ios bd claim t-2", ["t-1"]))

    def test_a_ticket_held_in_the_queue_blocks_a_claim_of_another(self):
        with task_queue.locked(self.path) as board:
            task_queue.start(board, "t-1", ["agent-ios"])
        with mock.patch.dict(os.environ, {"AGENT_SESSION": "agent-ios"}):
            self.assertEqual("agent-ios holds t-1 in the task queue", self.deny("bd update t-2 --claim"))
            self.assertIsNone(self.deny("bd update t-1 --claim"))

    def test_no_claim_or_no_known_session_passes(self):
        self.assertIsNone(self.deny("bd update t-2 --append-notes x", ["t-1"]))
        self.assertIsNone(self.deny("bd update t-2 --claim", ["t-1"]))
        self.assertIsNone(self.deny("bd show t-2; echo --claim", ["t-1"]))


if __name__ == "__main__":
    unittest.main()

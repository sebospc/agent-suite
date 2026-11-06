import unittest

import json

from cockpit.board.bd_board import parse_beads
from cockpit.team import Team, role_of_name


class TeamNamesTest(unittest.TestCase):
    team = Team(roles=["ios", "brain"], coordinating=["brain"], known_holders=[])

    def test_new_and_old_prefix_give_the_same_role(self):
        self.assertEqual(role_of_name("agent-ios"), "ios")
        self.assertEqual(role_of_name("old-ios"), "ios")
        self.assertEqual(role_of_name("claude-cloud"), "claude-cloud")

    def test_a_session_not_yet_restarted_still_counts_as_team(self):
        self.assertTrue(self.team.is_session("old-ios"))
        self.assertTrue(self.team.does_task_work("agent-ios"))
        self.assertFalse(self.team.does_task_work("agent-brain"))

    def test_the_cockpit_names_sessions_with_the_new_prefix(self):
        self.assertEqual(self.team.session_name("ios"), "agent-ios")

    def test_the_board_read_keeps_beads_of_the_renamed_prefix(self):
        export = "\n".join(json.dumps({"id": i, "title": "t", "status": "open"}) for i in ("mb-a1", "pg-a2", "x-a3"))
        self.assertEqual(["mb-a1", "pg-a2"], [b.id for b in parse_beads(export)])


if __name__ == "__main__":
    unittest.main()

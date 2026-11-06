import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launcher


def config_with_team(sessions):
    board = tempfile.mkdtemp()
    with open(os.path.join(board, "team.json"), "w") as handle:
        json.dump({"sessions": sessions}, handle)
    return {"board_dir": board, "team_json": "team.json", "session_prefix": "agent-"}


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.config = config_with_team({"agent-ios": {"launch": ["--model", "sonnet"]}, "lead": {}})

    def test_a_bare_resume_gets_its_saved_flags_back(self):
        saved = {"abc": ["--model", "opus", "--name", "agent-lead"]}
        self.assertEqual(["--model", "opus", "--name", "agent-lead", "--resume", "abc"],
                         launcher.with_launch_flags(["--resume", "abc"], self.config, "agent-lead", saved))

    def test_a_role_pane_names_the_session_and_a_fresh_launch_gets_the_role_flags(self):
        self.assertEqual(["--model", "sonnet", "--name", "agent-ios"],
                         launcher.with_launch_flags([], self.config, "ios", {}))
        self.assertEqual(["--effort", "low", "--name", "agent-lead"],
                         launcher.with_launch_flags(["--effort", "low"], self.config, "agent-lead", {}))

    def test_a_pane_that_is_no_role_or_a_launch_with_a_name_is_left_alone(self):
        self.assertEqual([], launcher.with_launch_flags([], self.config, "scratch", {}))
        self.assertEqual(["--name", "mine"], launcher.with_launch_flags(["--name", "mine"], self.config, "ios", {}))

    def test_saved_flags_drop_the_resume_pair(self):
        self.assertEqual(["--model", "opus"], launcher.without_resume(["--model", "opus", "--resume", "abc"]))


if __name__ == "__main__":
    unittest.main()

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config

BOARD_FILE = "board-file.json"


class SuiteConfigTest(unittest.TestCase):
    def project(self, config):
        folder = Path(tempfile.mkdtemp())
        (folder / "sub").mkdir()
        (folder / suite_config.FILE_NAME).write_text(json.dumps(config))
        return folder

    def test_found_from_a_subfolder_and_merged_over_the_defaults(self):
        folder = self.project({"board_dir": "/b", "courier": {"idle_minutes": 5}})
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(folder / "sub")}):
            os.environ.pop("AGENT_SUITE_CONFIG", None)
            config = suite_config.load()
        self.assertEqual(("/b", 5, 30), (config["board_dir"], config["courier"]["idle_minutes"],
                                         config["courier"]["cooldown_minutes"]))

    def test_an_unknown_key_stops_and_a_hook_falls_back_to_the_defaults(self):
        folder = self.project({"bord_dir": "/b"})
        with mock.patch.dict(os.environ, {"AGENT_SUITE_CONFIG": str(folder / suite_config.FILE_NAME)}):
            with self.assertRaisesRegex(suite_config.ConfigError, "unknown keys bord_dir"):
                suite_config.load()
            self.assertEqual(os.path.expanduser("~/.agent-board/" + BOARD_FILE),
                             suite_config.board_file("AGENT_UNSET_FOR_TEST", BOARD_FILE))

    def test_the_env_override_wins_and_a_bare_name_lives_in_the_board(self):
        folder = self.project({"board_dir": "/b"})
        with mock.patch.dict(os.environ, {"AGENT_SUITE_CONFIG": str(folder / suite_config.FILE_NAME), "AGENT_X": "/x"}):
            self.assertEqual("/x", suite_config.board_file("AGENT_X", BOARD_FILE))
            self.assertEqual("/b/" + BOARD_FILE, suite_config.board_file("AGENT_UNSET_FOR_TEST", BOARD_FILE))


if __name__ == "__main__":
    unittest.main()

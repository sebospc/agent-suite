import dataclasses
import os
import shutil
import sys
import tempfile
import unittest

from cockpit.asks.no_asks import NoAsks
from cockpit.board.bd_board import BdBoard
from cockpit.board.no_board import NoBoard
from cockpit.composition import asks_of, board_of, project_config
from cockpit.milestone.milestone_plan_files import MilestonePlanFiles
from cockpit.milestone.no_milestone_plan import NoMilestonePlan
from cockpit.not_used import NotUsed
from cockpit.project_config.config_error import ConfigError
from cockpit.project_config.config_schema import check_complete
from cockpit.snapshot.snapshot_builder import SnapshotBuilder
from tests.builders import FIXTURES, NOW, prices, team, thresholds
from tests.test_snapshot import builder

BEADS_CAT = [sys.executable, "-c", "import sys; sys.stdout.write(open(sys.argv[1]).read())", os.path.join(FIXTURES, "beads.sample.jsonl")]


def built_with(**ports) -> dict:
    standard = builder()
    return SnapshotBuilder(dataclasses.replace(standard.ports, **ports), team(), thresholds(), prices(), 5).build()


class NoneAdaptersTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()  # holds no dod.json or goal.json
        self.addCleanup(shutil.rmtree, self.folder)

    def test_no_board_leaves_the_milestone_out_and_is_not_a_broken_source(self):
        snapshot = built_with(board=NoBoard())
        self.assertEqual({"available": False, "absent": True}, snapshot["milestone"])
        self.assertTrue(snapshot["sources"]["board"]["absent"])
        self.assertEqual({""}, {row["tag"] for row in snapshot["sessions"]})
        self.assertTrue(snapshot["asks"]["available"])  # the rest still shows

    def test_no_panel_leaves_the_questions_out_and_refuses_an_answer(self):
        snapshot = built_with(asks=NoAsks())
        self.assertEqual((False, True), (snapshot["asks"]["available"], snapshot["asks"]["absent"]))
        self.assertEqual("M4", snapshot["milestone"]["name"])
        with self.assertRaises(NotUsed):
            NoAsks().answer("abc123", "yes")

    def test_no_milestone_reads_the_beads_without_dod_or_goal_and_leaves_the_milestone_out(self):
        board = BdBoard(self.folder, BEADS_CAT, 5, lambda: NOW, NoMilestonePlan())
        state = board.read()
        self.assertEqual((15, False), (len(state.beads), state.milestone_used))
        snapshot = built_with(board=board)
        self.assertEqual({"available": False, "absent": True}, snapshot["milestone"])
        self.assertTrue(snapshot["sources"]["board"]["ok"])

    def test_a_real_milestone_folder_without_its_files_is_still_a_broken_board(self):
        snapshot = built_with(board=BdBoard(self.folder, BEADS_CAT, 5, lambda: NOW, MilestonePlanFiles(self.folder)))
        self.assertIn("dod.json", snapshot["milestone"]["error"])
        self.assertNotIn("absent", snapshot["sources"]["board"])


class NoneAdapterConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = project_config()
        self.paths = self.config["paths"]

    def without(self, *keys) -> dict:
        return {k: v for k, v in self.paths.items() if k not in keys}

    def test_the_composition_picks_a_none_adapter_for_each_key_left_out(self):
        self.assertIsInstance(board_of(self.without("board_dir", "bd_command", "milestone_dir"), lambda: NOW), NoBoard)
        self.assertIsInstance(board_of(self.without("milestone_dir"), lambda: NOW).milestone_plan, NoMilestonePlan)
        self.assertIsInstance(board_of(self.paths, lambda: NOW).milestone_plan, MilestonePlanFiles)
        self.assertIsInstance(asks_of(dict(self.without("panel", "ask_owner")), lambda: NOW), NoAsks)

    def test_a_half_set_pair_fails_at_start(self):
        with self.assertRaises(ConfigError) as caught:
            check_complete(dict(self.config, paths=self.without("bd_command")), ".cockpit.json")
        self.assertIn("paths.board_dir is set but paths.bd_command is not", str(caught.exception))
        with self.assertRaises(ConfigError) as caught:
            check_complete(dict(self.config, paths=self.without("panel", "ask_owner")), ".cockpit.json")
        self.assertIn("paths.gate_logs reads the panel's scratch", str(caught.exception))
        check_complete(dict(self.config, paths=dict(self.without("panel", "ask_owner"), gate_logs="~/gates")), ".cockpit.json")


if __name__ == "__main__":
    unittest.main()

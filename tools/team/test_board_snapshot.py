import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board_snapshot
import suite_config


def config(**snapshot):
    board = tempfile.mkdtemp()
    os.mkdir(os.path.join(board, ".beads"))
    return {"board_dir": board, "lead": "lead", "session_prefix": "agent-", "snapshot": snapshot}


class BoardSnapshotTest(unittest.TestCase):
    def test_no_remote_means_no_plan(self):
        with self.assertRaisesRegex(suite_config.ConfigError, "snapshot.remote"):
            board_snapshot.plan(config())

    def test_the_secret_scan_runs_on_the_full_copy_before_anything_is_staged(self):
        labels = [label for label, _, _ in board_snapshot.plan(config(remote="git@host:me/board.git",
                                                                      memory_dirs={"memory": "~/m"}))]
        self.assertEqual(["clone", "pull", "board", "beads", "memory memory", "secret scan", "stage"], labels)

    def test_the_beads_store_and_backups_never_enter_the_copy(self):
        board = dict((label, argv) for label, argv, _ in board_snapshot.plan(config(remote="r")))["board"]
        for pattern in (".beads/", "*.bak*", ".beads-credential-key"):
            self.assertIn(f"--exclude={pattern}", board)


if __name__ == "__main__":
    unittest.main()

import os
import unittest

from cockpit.autopilot.task_folders import named_folders, shares_folder
from cockpit.transcripts.transcript_stats import first_reads, task_files


def request(t, *tools):
    return {"t_first": t, "tools": list(tools)}


class TaskFoldersTest(unittest.TestCase):
    def test_a_bead_names_its_scope_and_paths_but_not_slashed_prose_or_links(self):
        text = "scope: ~/Documents/agent-suite only\nfix cockpit/autopilot/rules.py; rtk/caveman/ponytail; https://x.com/a/b"
        self.assertEqual({os.path.expanduser("~/Documents/agent-suite"), "cockpit/autopilot"}, named_folders(text))

    def test_a_relative_folder_matches_inside_an_absolute_one(self):
        self.assertTrue(shares_folder(["cockpit/autopilot"], ["/u/old-cockpit/cockpit/autopilot/x"]))
        self.assertTrue(shares_folder(["/u/repo"], ["/u/repo/page"]))
        self.assertFalse(shares_folder(["/u/repo-b"], ["/u/repo"]))

    def test_task_files_are_the_last_finished_task_only(self):
        rows = [request(1, ("Read", "/old.py")), request(2, ("Bash", "bd close pg-a")), request(3, ("Edit", "/new.py")),
                request(4, ("Bash", "bd close pg-b")), request(5, ("Read", "/later.py"))]
        self.assertEqual({"/new.py"}, task_files(rows))
        self.assertEqual(frozenset(), task_files(rows[:1]))

    def test_first_reads_stop_at_the_fourth_turn(self):
        rows = [request(1, ("Read", "/a.py")), request(10, ("Read", "/b.py"))]
        self.assertEqual({"/a.py"}, first_reads(rows, [{"t": 0}, {"t": 2}, {"t": 3}, {"t": 5}]))


if __name__ == "__main__":
    unittest.main()

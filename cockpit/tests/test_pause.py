import os
import shutil
import tempfile
import unittest

from cockpit.pause.pause_file import PauseFile
from cockpit.pause.pause_view import pause_view
from tests.builders import HOUR, NOW, bead


class PauseTest(unittest.TestCase):
    def test_the_pause_file_exists_only_while_paused_and_keeps_its_time(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        switch = PauseFile(os.path.join(folder, "paused"))
        self.assertIsNone(switch.since())
        switch.set(True, NOW)
        self.assertEqual(NOW, switch.since())
        switch.set(False, NOW + 60)
        self.assertFalse(os.path.exists(os.path.join(folder, "paused")))

    def test_a_commit_or_a_claim_after_the_pause_shows_it_did_not_hold(self):
        claimed = bead("pg-a1", status="in_progress")
        claimed = claimed.__class__(**dict(claimed.__dict__, started_at=NOW - 60))
        view = pause_view(NOW - HOUR, [{"sha": "abc1234", "t": NOW - 30, "subject": "x"}, {"sha": "old", "t": NOW - 2 * HOUR}], [claimed], NOW)
        self.assertEqual((["abc1234"], ["pg-a1"], False), (view["commits"], view["claims"], view["holds"]))
        self.assertTrue(pause_view(NOW - HOUR, [], [], NOW)["holds"])
        self.assertEqual({"paused": False}, pause_view(None, [], [], NOW))


class TeamPauseToolTest(unittest.TestCase):
    def test_the_tool_writes_the_same_file_the_cockpit_reads(self):
        import importlib.util
        from unittest import mock
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        spec = importlib.util.spec_from_file_location("team_pause", os.path.join(os.path.dirname(__file__), "..", "tools", "team_pause.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        path = os.path.join(folder, "paused")
        with mock.patch.object(tool, "PauseFile", lambda _: PauseFile(path)):
            self.assertEqual(0, tool.main(["team_pause.py", "off"]))
            self.assertIsNotNone(PauseFile(path).since())
            self.assertEqual(0, tool.main(["team_pause.py", "on"]))
            self.assertIsNone(PauseFile(path).since())
            self.assertEqual(2, tool.main(["team_pause.py", "sideways"]))

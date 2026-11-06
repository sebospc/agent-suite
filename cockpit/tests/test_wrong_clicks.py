import unittest

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.autopilot.autopilot import Autopilot
from cockpit.classifier.fake_classifier import FakeClassifier
from cockpit.classifier.shadow import suggestions
from cockpit.classifier.verdict_state import World, session_version
from cockpit.clock.fixed_clock import FixedClock
from cockpit.controls.controls import Controls
from cockpit.milestone.tree import BeadTree
from cockpit.panes.fake_panes import FakePanes
from tests.builders import NOW, thresholds
from tests.test_autopilot import row
from tests.test_classifier import milestone, row as verdict_row, session



def pilot(**overrides):
    log, panes = FakeActionLog(), FakePanes()
    controls = Controls(panes, FixedClock(NOW), lambda line: None, log)
    autopilot = Autopilot(controls, thresholds(**{"autopilot_on": True, **overrides}), log, FixedClock(NOW), lambda line: None)
    return autopilot, controls, panes


def sent_id(autopilot, kind):
    return next(r["id"] for r in autopilot.action_log.records if r["event"] == "sent" and r["kind"] == kind)


class WrongClickTest(unittest.TestCase):
    def test_a_compaction_marked_wrong_keeps_only_the_label(self):
        autopilot, _, _ = pilot()
        autopilot.step([row()])
        decision = sent_id(autopilot, "compact")
        result = autopilot.mark_wrong(decision)
        self.assertEqual((True, False), (result["ok"], result["undo"]))
        self.assertIn("its context is gone", result["why"])
        self.assertEqual({"ok": False, "error": "Already marked wrong."}, autopilot.mark_wrong(decision))
        self.assertFalse(autopilot.mark_wrong("nope")["ok"])
        shown = autopilot.today()["rows"][0]
        self.assertTrue(shown["wrong"].startswith("Marked wrong: its context is gone"), shown["wrong"])
        self.assertEqual({"ios": [{"kind": "compact", "decision": autopilot.action_log.records[0]["reason"]}]}, autopilot.wrong_labels())

    def test_a_kept_task_shows_in_the_log_and_can_be_marked_wrong(self):
        autopilot, _, panes = pilot()
        warm = row(over=False, holds=0, kind="idle", spot=500_000, cache_ttl=3600, last_turn_at=NOW - 600)
        autopilot.step([warm], arriving={"ios": {"id": "t9", "bead": "pg-a1"}})
        kept = autopilot.today()["rows"][0]
        self.assertEqual(("task:t9", "kept"), (kept["id"], kept["state"]))
        self.assertTrue(autopilot.mark_wrong("task:t9")["ok"])
        self.assertEqual([], panes.typed)


class JevSeesWrongClicksTest(unittest.TestCase):
    def test_the_labels_are_in_its_state_and_a_new_one_asks_again(self):
        fake = FakeClassifier({"session ios": session()})
        tree = BeadTree([milestone()])
        rows = [verdict_row("ios", "no bead", holds=0)]
        suggestions(rows, tree, fake)
        labelled = World(wrongs={"ios": [{"kind": "clear", "decision": "TASK t1: starts fresh"}]})
        suggestions(rows, tree, fake, world=labelled)
        self.assertNotEqual(session_version(rows[0], [], World()), session_version(rows[0], [], labelled))  # re-asked
        self.assertEqual([{"kind": "clear", "decision": "TASK t1: starts fresh"}], fake.states["session ios"]["owner_marked_wrong"])


if __name__ == "__main__":
    unittest.main()

import unittest

from cockpit.autopilot.compact_verdicts import judge_compacts
from cockpit.autopilot.rules import HAIKU
from cockpit.transcripts.refill import refilled_after
from tests.builders import NOW


def sent(id_, reason, model_id="claude-haiku-5-5", t=NOW - 3600):
    return {"t": t, "event": "sent", "kind": "compact", "origin": "autopilot", "id": id_, "session": "coordinator",
            "reason": reason, "model_id": model_id}


def judge(records, costs, now=NOW):
    written, lines = [], []
    judge_compacts(records, [{"name": "coordinator", "compaction_costs": costs}], now, written.append, lines.append)
    return [(w["id"], w["event"]) for w in written]


class RefillTest(unittest.TestCase):
    def test_back_at_95_percent_of_its_size_within_15_minutes_is_a_refill(self):
        after = [{"t_first": 100.0, "context": 82_000}, {"t_first": 220.0, "context": 89_500}, {"t_first": 400.0, "context": 95_000}]
        self.assertEqual(120.0, refilled_after(after, 100.0, 94_000))
        self.assertIsNone(refilled_after(after, 100.0, 120_000))
        self.assertIsNone(refilled_after([{"t_first": 1100.0, "context": 95_000}], 100.0, 94_000))  # after the window


class HaikuVerdictTest(unittest.TestCase):
    """Panels f68cd6 to b31e2b: a Haiku compaction is judged by whether it was undone within 15 minutes, not marked right."""

    def test_a_refilled_haiku_compaction_is_wrong_and_one_that_held_is_right(self):
        at = NOW - 3600 + 30
        records = [sent("a", f"{HAIKU}: Haiku at 91k"), sent("b", "Compact idle sessions over their sweet spot: 95k", t=NOW - 3000)]
        costs = [{"at": at, "refilled_s": 160.0, "recovery": None, "saved": None},
                 {"at": NOW - 3000 + 30, "refilled_s": None, "recovery": None, "saved": None}]
        self.assertEqual([("a", "wrong_compact"), ("b", "right_compact")], judge(records, costs))

    def test_an_unmeasured_right_verdict_is_judged_again_and_a_measured_one_is_not(self):
        records = [sent("a", f"{HAIKU}: Haiku at 91k"),
                   {"t": NOW - 3500, "event": "right_compact", "id": "a", "session": "coordinator", "recovery": None, "saved": None}]
        costs = [{"at": NOW - 3600 + 30, "refilled_s": 160.0, "recovery": None, "saved": None}]
        self.assertEqual([("a", "wrong_compact")], judge(records, costs))
        measured = records + [{"t": NOW - 100, "event": "wrong_compact", "id": "a", "session": "coordinator", "refilled_s": 160.0}]
        self.assertEqual([], judge(measured, costs))

    def test_a_haiku_compaction_waits_out_its_window_before_it_is_called_right(self):
        records = [sent("a", f"{HAIKU}: Haiku at 91k", t=NOW - 300)]
        self.assertEqual([], judge(records, [{"at": NOW - 270, "refilled_s": None, "recovery": None, "saved": None}]))

    def test_an_opus_compaction_is_still_judged_by_its_recovery_cost(self):
        records = [sent("o", "Compact at the next finished turn over the ceiling", model_id="claude-opus-5-5")]
        cost = {"at": NOW - 3600 + 30, "refilled_s": None, "recovery": 900, "saved": 500}
        self.assertEqual([("o", "wrong_compact")], judge(records, [cost]))
        self.assertEqual([], judge(records, [dict(cost, recovery=None, saved=None)]))


if __name__ == "__main__":
    unittest.main()

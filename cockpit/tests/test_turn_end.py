import unittest

from cockpit.autopilot.rules import CEILING, decide, skipped
from cockpit.autopilot.turn_end import TURN_END
from tests.builders import NOW, thresholds


def row(**fields):
    base = {"name": "brain", "state": "idle", "pane": "w1:p1", "model": "Opus 5.5", "model_id": "claude-opus-5-5", "context": 160_000,
            "spot": 188_000, "ceiling": 235_000, "over": False, "notes_saved": False, "holds": 0, "last_turn_at": NOW - 25,
            "cache_ttl": 3600, "effort": "high", "session_id": "s1", "refills": [20_000, 22_000], "base": 20_000}
    base.update(fields)
    return base


def rules(rows):
    return [c["rule"] for c in decide(rows, set(), thresholds(), NOW)]


class TurnEndTest(unittest.TestCase):
    """Panels f68cd6 to b31e2b: compact at a finished turn over min(sweet spot, 150k) instead of waiting for the ceiling;
    the replay of 7 days put the cost bottom at 150k and the ceilings cut sessions at 210k to 274k."""

    def test_a_session_over_150k_is_compacted_once_its_turn_has_ended(self):
        self.assertEqual([TURN_END], rules([row()]))
        self.assertEqual([], rules([row(last_turn_at=NOW - 10)]))  # 10 s: between two tool calls, not a finished turn
        self.assertEqual([], rules([row(context=140_000)]))
        self.assertEqual([], rules([row(state="busy")]))

    def test_its_sweet_spot_is_the_line_when_it_is_under_150k(self):
        self.assertEqual([TURN_END], rules([row(spot=120_000, context=130_000)]))
        self.assertEqual([], rules([row(spot=120_000, context=110_000)]))

    def test_the_ceiling_stays_the_backstop(self):
        self.assertEqual([CEILING], rules([row(context=240_000)]))

    def test_haiku_has_no_turn_line(self):
        self.assertEqual([], rules([row(model="Haiku 5.5", model_id="claude-haiku-5-5", spot=90_000, context=95_000)]))

    def test_the_thrash_guard_and_a_base_over_the_line_hold_it(self):
        self.assertEqual([], rules([row(refills=[155_000, 158_000])]))
        self.assertEqual([], rules([row(base=152_000)]))

    def test_unsaved_notes_do_not_hold_it_and_a_missed_window_goes_to_the_expiry_rule(self):
        self.assertEqual([TURN_END], rules([row(notes_saved=False, holds=1)]))
        self.assertEqual([], rules([row(last_turn_at=NOW - 15 * 60)]))  # under its spot: nothing until a TASK

    def test_a_turn_that_just_ended_says_when_it_compacts(self):
        why = [s["why"] for s in skipped([row(last_turn_at=NOW - 5)], set(), thresholds(), NOW) if s["rule"] == TURN_END]
        self.assertEqual(["its turn ended 5 s ago; it compacts once idle 20 s"], why)


if __name__ == "__main__":
    unittest.main()

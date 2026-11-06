import unittest

from cockpit.sessions.session_row import context_boost
from cockpit.thresholds import Thresholds


def thresholds(until: str) -> Thresholds:
    return Thresholds({"context_boost": {"value": {"brain": {"factor": 3, "until": until}}}})


class ContextBoostTest(unittest.TestCase):
    def test_boosts_only_the_named_session_until_its_end(self):
        self.assertEqual(context_boost("brain", thresholds("2999-01-01T00:00:00Z")), 3)
        self.assertEqual(context_boost("ios", thresholds("2999-01-01T00:00:00Z")), 1)
        self.assertEqual(context_boost("brain", thresholds("2000-01-01T00:00:00Z")), 1)
        self.assertEqual(context_boost("brain", Thresholds({})), 1)

    def test_a_boost_with_no_end_date_stays(self):
        no_end = Thresholds({"context_boost": {"value": {"brain": {"factor": 2}}}})
        self.assertEqual(context_boost("brain", no_end), 2)
        self.assertEqual(context_boost("ai", no_end), 1)

import unittest

from cockpit.sessions.start_limit import start_limit
from cockpit.transcripts.transcript_stats import start_load


class StartLoadTest(unittest.TestCase):
    def test_the_first_message_is_taken_out_of_the_first_request(self):
        rows = [{"t_first": 100.0, "context": 40_000}]
        self.assertEqual(40_000 - 1000, start_load(rows, [{"t": 99.0, "chars": 3500}]))
        self.assertEqual(40_000, start_load(rows, []))
        self.assertIsNone(start_load([], []))

    def test_a_roles_limit_comes_from_its_own_usual(self):
        self.assertEqual({"usual": 30_000, "limit": 36_000, "starts": 3}, start_limit([28_000, 30_000, 35_000], 20))
        self.assertIsNone(start_limit([30_000, 31_000], 20))  # too few starts to know its usual

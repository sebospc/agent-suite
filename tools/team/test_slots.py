import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slots
from task_queue import Refused

KNOWN = {"heavy-build": {"minutes": 40}, "test-db": {}}


class SlotsTest(unittest.TestCase):
    def test_one_holder_then_a_waiting_line_granted_in_order(self):
        board = {}
        self.assertEqual("granted heavy-build to a", slots.request(board, KNOWN, "heavy-build", "a", 0, "", 0))
        self.assertIn("b waits, number 1", slots.request(board, KNOWN, "heavy-build", "b", 0, "", 1))
        self.assertIn("c waits, number 2", slots.request(board, KNOWN, "heavy-build", "c", 0, "", 2))
        self.assertIn("granted to b", slots.free(board, "heavy-build", "a", 3))
        self.assertEqual("b", board["heavy-build"]["holder"]["session"])
        self.assertEqual(40, board["heavy-build"]["holder"]["minutes"])

    def test_slots_are_independent_and_unknown_names_are_refused(self):
        board = {}
        slots.request(board, KNOWN, "heavy-build", "a", 0, "", 0)
        self.assertEqual("granted test-db to b", slots.request(board, KNOWN, "test-db", "b", 0, "", 0))
        with self.assertRaisesRegex(Refused, "no slot named sim"):
            slots.request(board, KNOWN, "sim", "a", 0, "", 0)
        with self.assertRaisesRegex(Refused, "b does not hold heavy-build"):
            slots.free(board, "heavy-build", "b", 0)

    def test_a_hold_past_twice_its_minutes_is_overdue(self):
        board = {}
        slots.request(board, KNOWN, "test-db", "a", 10, "", 0)
        self.assertEqual([], slots.overdue(board, 20 * 60))
        self.assertEqual(["test-db held by a for 21 min"], slots.overdue(board, 21 * 60))


if __name__ == "__main__":
    unittest.main()

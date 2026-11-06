import unittest
from datetime import datetime

from tests.builders import prices
from tests.test_sessions import row


class CompactionDriftGoneTest(unittest.TestCase):
    def test_a_compaction_off_its_window_marks_nothing(self):  # the owner a4e769 took the drift line out of the detail
        self.assertEqual([], row(150_000)["marks"])


class PriceMarkTest(unittest.TestCase):
    def test_prices_are_marked_after_90_days(self):
        table = prices()
        as_of = datetime.fromisoformat(table.as_of).timestamp()
        self.assertEqual("", table.stale_mark(as_of + 90 * 86400 + 3600, 90))
        self.assertIn("91 days ago", table.stale_mark(as_of + 91 * 86400 + 3600, 90))

    def test_a_model_without_a_price_is_marked(self):
        self.assertIn("no price for claude-opus-4-8", row(150_000, model="claude-opus-4-8")["marks"])


if __name__ == "__main__":
    unittest.main()

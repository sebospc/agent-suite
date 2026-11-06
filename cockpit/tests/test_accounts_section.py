import time
import unittest

from cockpit.snapshot.accounts_section import reset_time
from tests.builders import HOUR, NOW


class ResetTimeTest(unittest.TestCase):
    def test_a_reset_on_another_day_shows_its_date_with_the_day_number(self):
        later = NOW + 3 * 24 * HOUR
        self.assertEqual(time.strftime("%b %-d, %H:%M", time.localtime(later)), reset_time(later, NOW))
        self.assertRegex(reset_time(later, NOW), r"^[A-Z][a-z]{2} \d{1,2}, \d\d:\d\d$")

    def test_a_reset_today_shows_the_clock_only(self):
        midnight = time.mktime(time.localtime(NOW)[:3] + (0, 0, 0, 0, 0, -1))
        self.assertRegex(reset_time(midnight + 60, midnight + 30), r"^\d\d:\d\d$")
        self.assertEqual("", reset_time(None, NOW))


if __name__ == "__main__":
    unittest.main()

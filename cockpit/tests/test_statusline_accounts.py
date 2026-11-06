import json
import tempfile
import unittest

from cockpit.accounts.statusline_accounts import StatuslineAccounts
from cockpit.snapshot.accounts_section import accounts_section
from cockpit.source_unavailable import SourceUnavailable
from tests.builders import thresholds


class StatuslineAccountsTest(unittest.TestCase):
    def test_reads_the_status_line_limits_as_one_active_account(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as saved:
            json.dump({"rate_limits": {"five_hour": {"used_percentage": 63, "resets_at": 1793905200},
                                       "seven_day": {"used_percentage": 50, "resets_at": 1794196800}}, "at": 1000.0}, saved)
        [account] = StatuslineAccounts(saved.name, now=lambda: 1030.0).list()
        self.assertEqual((account.five_hour_pct, account.five_hour_resets, account.seven_day_pct, account.age_seconds),
                         (63.0, 1793905200.0, 50.0, 30.0))
        self.assertTrue(account.active)
        # The live sessions call ~/.claude's login "default"; the one account row lists them instead of "no team session".
        rows = [{"name": "brain", "account": "default"}, {"name": "ios", "account": "default"}]
        self.assertEqual("brain, ios", accounts_section([account], rows, thresholds(), 1030.0)[0]["sessions"])

    def test_no_saved_limits_is_an_unavailable_source(self):
        with self.assertRaises(SourceUnavailable):
            StatuslineAccounts("/nonexistent/usage.json").list()


if __name__ == "__main__":
    unittest.main()

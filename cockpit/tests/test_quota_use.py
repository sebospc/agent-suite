import unittest

from cockpit.metrics.quota_use import QuotaUse, points_used
from cockpit.source_unavailable import SourceUnavailable
from tests.builders import NOW


def snapshot(tasks=4):
    return {"accounts": [{"number": "3", "seven_day": 40.0}, {"number": "2", "seven_day": None}],
            "sessions": [{"name": "ios", "account": "3"}, {"name": "brain", "account": "3"}, {"name": "x", "account": ""}],
            "health": [{"id": "outcomes", "table": {"rows": [{"session": "ios", "tasks": tasks}, {"session": "brain", "tasks": 0}]}}]}


class QuotaUseTest(unittest.TestCase):
    def test_points_are_the_rises_and_a_weekly_reset_is_not_spending(self):
        self.assertEqual(7.0, points_used([[0, 30.0], [1, 33.0], [2, 2.0], [3, 6.0], [4, None]]))

    def test_points_per_finished_task_per_account_feed_jev(self):
        asked = []
        quota = QuotaUse(lambda area, row, key, start: asked.append((area, row, key)) or [[start, 30.0], [NOW, 40.0]])
        found = quota.step(snapshot(), NOW)
        self.assertEqual(("2.5 points per task", "ok"), (found["value"], found["level"]))
        self.assertEqual([("quota_use", "acct-3", "seven_day")], asked)  # an account with no reading is not read
        self.assertEqual({"3": 2.5}, quota.per_account)
        quota.step(snapshot(), NOW + 60)
        self.assertEqual(1, len(asked))  # the history is read every 10 min, not every read

    def test_no_finished_task_or_an_unreadable_history_says_unknown(self):
        full = lambda area, row, key, start: [[start, 30.0], [NOW, 40.0]]
        self.assertEqual("unknown", QuotaUse(full).step(snapshot(tasks=0), NOW)["level"])
        young = lambda area, row, key, start: [[NOW - 600, 30.0], [NOW, 40.0]]  # its history began 10 min ago
        self.assertEqual("unknown", QuotaUse(young).step(snapshot(), NOW)["level"])
        def broken(*args):
            raise SourceUnavailable("metrics.jsonl: gone")
        self.assertEqual(("unknown", "metrics.jsonl: gone"), tuple(QuotaUse(broken).step(snapshot(), NOW)[k] for k in ("level", "why")))


if __name__ == "__main__":
    unittest.main()

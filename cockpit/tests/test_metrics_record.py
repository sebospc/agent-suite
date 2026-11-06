import unittest

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.metrics.metrics_record import MetricsRecord
from cockpit.snapshot.health_tables import table
from cockpit.source_unavailable import SourceUnavailable
from cockpit.tokens.tokens_section import tokens_section
from cockpit.snapshot.health_tables import tokens_table
from cockpit.transcripts.history import History, Request
from tests.builders import NOW, prices, team, thresholds


def tokens_area(rows, totals=()):
    return {"id": "tokens", "table": table("", [("input", "Input", "tokens")], rows, list(totals))}


class BrokenLog(FakeActionLog):
    def append(self, record):
        raise SourceUnavailable("disk full")


class MetricsRecordTest(unittest.TestCase):
    def test_each_read_writes_one_line_with_only_the_rows_that_changed_and_a_gone_row_as_null(self):
        log = FakeActionLog()
        metrics = MetricsRecord(log)
        metrics.record([tokens_area([{"id": "ios", "input": 10}, {"id": "ai", "input": 5}], [("today", "Today", "tokens", 15)])], 100)
        metrics.record([tokens_area([{"id": "ios", "input": 10}, {"id": "ai", "input": 7}], [("today", "Today", "tokens", 17)])], 130)
        metrics.record([tokens_area([{"id": "ai", "input": 7}], [("today", "Today", "tokens", 17)])], 160)
        metrics.record([tokens_area([{"id": "ai", "input": 7}], [("today", "Today", "tokens", 17)])], 190)
        self.assertEqual([{"ios": {"input": 10}, "ai": {"input": 5}, "_totals": {"today": 15}},
                          {"ai": {"input": 7}, "_totals": {"today": 17}}, {"ios": None}, None],
                         [r["areas"].get("tokens") for r in log.records])
        self.assertEqual([100, 130, 160, 190], [r["t"] for r in log.records])

    def test_a_history_lists_each_change_and_starts_with_the_value_it_held_at_its_start(self):
        log = FakeActionLog()
        metrics = MetricsRecord(log)
        for t, value in ((100, 5), (130, 5), (160, 9), (190, 9), (220, 4)):
            metrics.record([tokens_area([{"id": "ai", "input": value}])], t)
        self.assertEqual([[100, 5], [160, 9], [220, 4]], metrics.history("tokens", "ai", "input", 0))
        self.assertEqual([[150, 5], [160, 9], [220, 4]], metrics.history("tokens", "ai", "input", 150))
        self.assertEqual([], metrics.history("tokens", "ios", "input", 0))

    def test_after_a_failed_write_the_next_line_holds_every_row_again(self):
        log = FakeActionLog()
        metrics = MetricsRecord(log)
        metrics.log = BrokenLog()
        with self.assertRaises(SourceUnavailable):
            metrics.record([tokens_area([{"id": "ai", "input": 5}])], 100)
        metrics.log = log
        metrics.record([tokens_area([{"id": "ai", "input": 5}])], 130)
        self.assertEqual({"ai": {"input": 5}}, log.records[0]["areas"]["tokens"])

    def test_a_lights_extra_tables_are_recorded_under_their_own_ids(self):
        log = FakeActionLog()
        area = tokens_area([{"id": "ios", "input": 1}])
        area["more"] = [dict(table("", [("n", "N", "count")], [{"id": "ios", "n": 2}]), id="tokens.landed")]
        MetricsRecord(log).record([area], 100)
        self.assertEqual({"ios": {"n": 2}}, log.records[0]["areas"]["tokens.landed"])


class TokensTableTest(unittest.TestCase):
    def test_input_is_what_is_left_after_cache_reads_writes_and_output_and_cost_uses_each_requests_card(self):
        history = History([Request(t=NOW - 60, session="agent-ios", tokens=1_000_000, context=50_000, origin="person", turn="a",
                                   read=600_000, out=100_000, write=200_000, model="claude-opus-5-5")])
        row = {"name": "ios", "spot": 100_000, "state": "idle", "context": 50_000, "cache_ttl": 3600, "account": "3",
               "model": "Opus 5.5", "per_task": 400_000}
        section = tokens_section([row], history, [], None, team(), thresholds(), NOW, prices())
        cells = tokens_table(section)["rows"][0]
        self.assertEqual((100_000, 100_000, 600_000, 200_000), (cells["input"], cells["output"], cells["cache_read"], cells["cache_write"]))
        # Opus 5.5 per M: input 4, 1 h write 8, cache read 0.20, output 20.
        self.assertEqual(round(0.1 * 4 + 0.2 * 8 + 0.6 * 0.2 + 0.1 * 20, 2), cells["cost"])
        self.assertEqual(("3", 400_000), (cells["account"], cells["per_task"]))

    def test_a_request_with_no_price_card_leaves_the_cost_unknown_instead_of_partial(self):
        history = History([Request(t=NOW - 60, session="agent-ios", tokens=10, context=1, origin="own", turn="a", model="claude-x")])
        row = {"name": "ios", "spot": None, "state": "idle", "context": 1}
        self.assertIsNone(tokens_section([row], history, [], None, team(), thresholds(), NOW, prices())["sessions"][0]["cost"])


if __name__ == "__main__":
    unittest.main()

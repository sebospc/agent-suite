import unittest
from dataclasses import replace

from cockpit.snapshot.outcome_lights import good_use_light, outcomes_light
from cockpit.transcripts.history import History, PeerMessage
from cockpit.transcripts.session_stats import Compaction
from cockpit.transcripts.transcript_stats import expired_writes
from tests.builders import NOW
from tests.test_sessions import stats


class OutcomeLightsTest(unittest.TestCase):
    def test_outcomes_count_per_session_what_the_decisions_led_to(self):
        named = {"ios": replace(stats(90_000), tasks_closed=2, tokens_24h=600_000, re_reads=3)}
        week = {"ios": {"task_starts": {"keep": 2, "clear": 1}, "wrong_clears": 1, "wrong": 0}}
        hold = PeerMessage(t=NOW - 3600, to="agent-ios", type="HOLD", bead="pg-a1", in_format=True, digest="d", tokens=0)
        found = outcomes_light(named, week, History(messages=[hold]), NOW)
        row = found["table"]["rows"][0]
        self.assertEqual((2, 300_000, 3, 1, 1, "clear 1, keep 2"),
                         (row["tasks"], row["per_task"], row["re_reads"], row["wrong_clears"], row["holds"], row["decisions"]))
        self.assertEqual(("watch", "0 wrong, 1 lost"), (found["level"], found["value"]))
        self.assertEqual("ok", outcomes_light(named, {}, None, NOW)["level"])

    def test_good_use_shows_cache_served_expired_writes_and_its_own_compactions(self):
        s = replace(stats(90_000), cache_read_24h=900_000, cache_write_24h=100_000, expired_writes_24h=40_000,
                    compactions=[Compaction(at=NOW - 600, trigger="auto", pre=190_000, post=20_000, first_context=None, first_cached=None)])
        found = good_use_light([{"name": "ios", "over": True}], {"ios": s}, NOW)
        self.assertEqual(("watch", "90% from cache, 40k expired"), (found["level"], found["value"]))
        self.assertEqual((90, 40_000, True, 1), tuple(found["table"]["rows"][0][k] for k in ("served", "expired", "over", "itself")))

    def test_a_write_counts_as_expired_only_when_nothing_came_within_the_cache_life(self):
        rows = [{"t_first": NOW - 5000, "t_last": NOW - 5000, "write": 10}, {"t_first": NOW - 4900, "t_last": NOW - 4900, "write": 20},
                {"t_first": NOW - 100, "t_last": NOW - 100, "write": 30}]
        self.assertEqual(20, expired_writes(rows, 3600, NOW - 86400, NOW))      # the last one is still alive
        self.assertEqual(50, expired_writes(rows, 3600, NOW - 86400, NOW + 3700))


if __name__ == "__main__":
    unittest.main()


class NotesWordTest(unittest.TestCase):
    def test_state_file_reread_reads_yes_no_or_why_not_known(self):
        from cockpit.snapshot.outcome_lights import notes_word
        self.assertEqual(["no state file", "no turn since its start", "yes", "no"],
                         [notes_word({}), notes_word({"memory_file": "s.md", "notes_reread": None}),
                          notes_word({"memory_file": "s.md", "notes_reread": True}), notes_word({"memory_file": "s.md", "notes_reread": False})])

import unittest

from cockpit.autopilot.compact_text import SHORT_SUMMARY
from cockpit.autopilot.rules import decide
from tests.builders import NOW, thresholds
from tests.test_autopilot import row


class CompactTextTest(unittest.TestCase):
    def test_a_haiku_session_is_asked_for_a_short_summary_and_the_others_get_a_plain_compact(self):
        # The coordinator re-reads ~54k after each compaction against a ~98k window; its summary was 8k of it (panels f68cd6 to b31e2b).
        haiku = row(name="coordinator", model="Haiku 5.5", model_id="claude-haiku-5-5", spot=60_000, context=70_000)
        self.assertEqual([SHORT_SUMMARY], [c["text"] for c in decide([haiku], set(), thresholds(), NOW)])
        self.assertTrue(SHORT_SUMMARY.startswith("/compact "))
        self.assertEqual(["/compact"], [c["text"] for c in decide([row()], set(), thresholds(), NOW)])


if __name__ == "__main__":
    unittest.main()

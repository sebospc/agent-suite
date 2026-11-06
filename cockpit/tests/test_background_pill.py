import unittest

from cockpit.live_sessions.background_pill import background_of

RULE = "─" * 40
# brain's and the coordinator's panes, 2026-11-05: the pill sits after the mode, agents are listed under it.
BRAIN = "\n".join(["  I start 2 shells next.", RULE, "❯ ", RULE, "  Opus 5.5 | project@main | 246k/1m (24%)",
                   "  ⏵⏵ bypass permissions on · 1 shell", "", "  ⏺ main", "  ◯ general-purpose  Reading  9m 10s"])
COORDINATOR = "\n".join([RULE, "❯ ", RULE, "  Haiku 5.5 | project@main | 78k/1m (7%)", "  ⏵⏵ bypass permissions on (shift+tab to cycle)"])


class BackgroundPillTest(unittest.TestCase):
    def test_reads_the_pill_under_the_input_box_and_never_a_reply_above_it(self):
        self.assertEqual("1 shell", background_of(BRAIN))
        self.assertEqual("", background_of(COORDINATOR))
        self.assertEqual("3 background tasks", background_of("  ⏵⏵ accept edits on · 3 background tasks"))


if __name__ == "__main__":
    unittest.main()

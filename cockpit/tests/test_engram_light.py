import unittest

from cockpit.snapshot.engram_light import engram_light


def read(status="ok", issues=(), loaded=("s1",)):
    return {"doctor": {"status": status, "issues": list(issues)}, "memories": {"total": 279, "saved_by_sessions": 1, "saved_today": 1},
            "sessions": {sid: {"loaded": sid in loaded, "searches": 2 if sid in loaded else 0, "saves": 0} for sid in ("s1", "s2")}}


ROWS = [{"name": "agent-brain", "state": "working", "session_id": "s1"}, {"name": "agent-ios", "state": "idle", "session_id": "s2"},
        {"name": "agent-design", "state": "off", "session_id": ""}]


class EngramLightTest(unittest.TestCase):
    def test_a_running_session_without_engram_is_watched_by_name(self):
        got = engram_light(read(), ROWS)
        self.assertEqual(("watch", "1/2 on, 1 saved today"), (got["level"], got["value"]))
        self.assertIn("agent-ios not on Engram yet", got["why"])

    def test_a_doctor_issue_asks_for_action(self):
        got = engram_light(read(issues=["orphaned relation"], loaded=("s1", "s2")), ROWS)
        self.assertEqual("act", got["level"])
        self.assertIn("orphaned relation", got["why"])

    def test_every_running_session_on_engram_and_a_clean_doctor_is_quiet(self):
        self.assertEqual("ok", engram_light(read(loaded=("s1", "s2")), ROWS)["level"])

    def test_a_stopped_session_is_not_counted(self):
        names = [r["session"] for r in engram_light(read(), ROWS)["table"]["rows"]]
        self.assertEqual(["agent-brain", "agent-ios"], names)


if __name__ == "__main__":
    unittest.main()

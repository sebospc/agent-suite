import unittest

from cockpit.mac.system_mac import elapsed_seconds, orphans
from cockpit.snapshot.mac_light import mac_light

ROWS = [{"name": "agent-brain", "state": "working", "session_id": "s1"}, {"name": "agent-ios", "state": "idle", "session_id": "s2"},
        {"name": "agent-design", "state": "off", "session_id": ""}]


def read(free=75, left=(), versions=None):
    return {"memory_free_pct": free, "swap_used_mb": 3507.0, "orphans": list(left), "claude_version": "2.1.318",
            "session_versions": versions or {"s1": "2.1.318", "s2": "2.1.318"}}


class MacLightTest(unittest.TestCase):
    def test_a_quiet_mac_is_ok(self):
        got = mac_light(read(), ROWS, 20, 10)
        self.assertEqual(("ok", "75% memory free"), (got["level"], got["value"]))

    def test_low_memory_asks_for_action(self):
        self.assertEqual("act", mac_light(read(free=8), ROWS, 20, 10)["level"])
        self.assertEqual("watch", mac_light(read(free=15), ROWS, 20, 10)["level"])

    def test_a_session_on_an_older_claude_code_is_watched_by_name(self):
        got = mac_light(read(versions={"s1": "2.1.318", "s2": "2.1.301"}), ROWS, 20, 10)
        self.assertEqual("watch", got["level"])
        self.assertIn("agent-ios on an older Claude Code", got["why"])

    def test_a_process_left_behind_is_listed_with_its_pid(self):
        got = mac_light(read(left=[{"pid": 86311, "age_s": 23 * 86400, "args": "tail -F /tmp/claude-501/x.out"}]), ROWS, 20, 10)
        self.assertEqual("watch", got["level"])
        self.assertIn({"id": "pid-86311", "what": "pid 86311", "detail": "tail -F /tmp/claude-501/x.out", "age": "23 d"},
                      got["table"]["rows"])


PS_LINES = ["86311     1 23-14:20:45 tail -n 0 -F /private/tmp/claude-501/s/y.out",
            "44608     1 31-22:10:05 /Users/me/.local/bin/herdr server",
            "19134     1 25-18:50:59 /bin/bash /Users/me/.local/bin/sec-loop",
            "70001  4242 30-00:00:00 grep -r x .",
            "70002     1    02:10:00 rg needle",
            "70003     1 2-00:00:00 /usr/bin/python3 /private/tmp/claude-501/s/watch.py"]


class OrphansTest(unittest.TestCase):
    def test_only_old_one_shot_tools_or_scratchpad_processes_whose_parent_is_launchd(self):
        self.assertEqual([86311, 70003], [o["pid"] for o in orphans(PS_LINES, 86400)])

    def test_ps_elapsed_time_forms(self):
        self.assertEqual([5, 125, 3725, 2 * 86400 + 3725], [elapsed_seconds(e) for e in ("00:05", "02:05", "01:02:05", "2-01:02:05")])


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from dataclasses import replace

from cockpit.autopilot.autopilot import Autopilot
from cockpit.autopilot.relaunch import relaunch_command
from cockpit.clock.fixed_clock import FixedClock
from cockpit.controls.controls import Controls
from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.panes.fake_panes import FakePanes
from tests.builders import NOW, thresholds
from tests.test_autopilot import row
from tests.test_sessions import stats

LAUNCH = ["--dangerously-skip-permissions", "--settings", "~/.agent-board/brain-launch/settings.json"]
SETTINGS = os.path.expanduser("~/.agent-board/brain-launch/settings.json")


def brain(**fields):
    return row(**{"name": "brain", "kind": "role", "holds": 0, "over": False, "context": 90_000, "session_id": "b1", "pane": "w4:p3",
                  "cache_ttl": 3600, "last_turn_at": NOW - 3700, "launch": LAUNCH, "flags": [], **fields})


def pilot(log=None):
    log, panes = log or FakeActionLog(), FakePanes()
    controls = Controls(panes, FixedClock(NOW), lambda line: None, log)
    return Autopilot(controls, thresholds(autopilot_on=True), log, FixedClock(NOW), lambda line: None), controls, panes


class RelaunchTest(unittest.TestCase):
    def test_a_cold_session_without_its_team_json_flags_is_never_relaunched(self):
        # Owner 2026-10-19: the autopilot does /compact and /clear only, never /exit.
        autopilot, _, panes = pilot()
        self.assertEqual(0, autopilot.step([brain()]))
        self.assertEqual([], panes.typed)

    def test_a_warm_cache_or_the_flags_already_there_send_nothing(self):
        autopilot, _, panes = pilot()
        self.assertEqual(0, autopilot.step([brain(last_turn_at=NOW - 600)]))
        self.assertEqual(0, autopilot.step([brain(flags=["--settings", SETTINGS])]))
        self.assertEqual([], panes.typed)

    def test_the_command_quotes_what_the_shell_would_split(self):
        self.assertEqual("Q_TERM=1 claude --resume b1 --settings '/a b/s.json'",
                         relaunch_command({"session_id": "b1", "launch": ["--settings", "/a b/s.json"]}))


if __name__ == "__main__":
    unittest.main()


class FullFlagsTest(unittest.TestCase):
    def test_a_session_with_no_launch_list_keeps_the_team_default_and_its_name(self):
        from cockpit.autopilot.relaunch import relaunch_command
        self.assertEqual("Q_TERM=1 claude --resume c1 --dangerously-skip-permissions --name agent-cockpit",
                         relaunch_command({"name": "cockpit", "session_id": "c1", "launch": []}))
        named = relaunch_command({"name": "brain", "session_id": "b1", "launch": ["--name", "agent-brain"]})
        self.assertEqual(1, named.count("--name"))


class LiveArgvTest(unittest.TestCase):
    """Brain, pg-o1sq relaunch HOLD 5f13ab8: the live command line decides, not the cockpit's own relaunch log."""

    def test_a_live_argv_with_every_flag_sends_nothing(self):
        autopilot, _, panes = pilot()
        live = ["--dangerously-skip-permissions", "--name", "agent-brain", "--settings", SETTINGS]
        self.assertEqual(0, autopilot.step([brain(flags=live, flags_known=True)]))
        self.assertEqual([], panes.typed)

    def test_without_its_argv_only_the_flags_ps_shows_are_checked(self):
        autopilot, _, panes = pilot()
        self.assertEqual(0, autopilot.step([brain(flags=["--settings", SETTINGS], flags_known=False)]))
        self.assertEqual([], panes.typed)

    def test_options_spell_out_short_and_equals_forms_and_skip_the_prompt(self):
        from cockpit.sessions.launch_options import options
        self.assertEqual([("--name", "agent-x"), ("--dangerously-skip-permissions", ""), ("--model", "opus")],
                         options(["-n", "agent-x", "--dangerously-skip-permissions", "--model=opus", "continue where you left off"]))

import unittest
from dataclasses import replace

from cockpit.action_log.day_log import day_rows
from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.clock.fixed_clock import FixedClock
from cockpit.controls.controls import Controls
from cockpit.controls.permission import command_for
from cockpit.panes.fake_panes import FakePanes
from cockpit.transcripts.session_stats import Compaction
from tests.builders import NOW
from tests.test_sessions import stats


def row(**fields):
    base = {"name": "ios", "state": "idle", "pane": "w1:p2", "can_compact": True, "why": "", "holds": 0, "notes_saved": None,
            "effort": "high", "context": 400_000, "session_id": "s1"}
    base.update(fields)
    return base


def controls(clock=None, fails=False):
    panes = FakePanes(fails)
    return Controls(panes, clock or FixedClock(NOW), lambda line: None, FakeActionLog()), panes


class PermissionTest(unittest.TestCase):
    def test_compact_follows_the_sessions_own_permission(self):
        self.assertEqual(("/compact", ""), command_for("compact", row()))
        self.assertEqual((None, "Busy. Compact it when its turn ends."), command_for("compact", row(can_compact=False, why="Busy. Compact it when its turn ends.")))

    def test_clear_only_at_a_task_end(self):
        self.assertEqual("/clear", command_for("clear", row())[0])
        self.assertIsNone(command_for("clear", row(holds=1))[0])
        self.assertIsNone(command_for("clear", row(state="busy"))[0])
        self.assertIsNone(command_for("clear", row(notes_saved=False))[0])

    def test_effort_takes_a_known_level_that_differs(self):
        self.assertEqual("/effort medium", command_for("effort", row(), "medium")[0])
        self.assertIsNone(command_for("effort", row(), "high")[0])
        self.assertIsNone(command_for("effort", row(), "max")[0])

    def test_nothing_goes_to_a_session_without_a_pane(self):
        self.assertIsNone(command_for("compact", row(pane=""))[0])
        self.assertIsNone(command_for("compact", row(state="off"))[0])


class ControlsTest(unittest.TestCase):
    def test_todays_log_holds_the_owners_controls_with_their_proof_and_not_the_autopilots(self):
        c, _ = controls()
        c.act("compact", "ios", "", [row()])
        c.send(row(name="ai"), "compact", "/compact", "", "autopilot", "over its sweet spot")
        proof = replace(stats(60_000), compactions=[Compaction(NOW + 60, "manual", 400_000, 60_000, None, None)])
        c.effects([row(), row(name="ai")], {"s1": proof}, NOW + 120)
        today = c.today()
        self.assertEqual([("ios", "done", 340_000)], [(r["session"], r["state"], r["cut"]) for r in today["rows"]])

    def test_a_control_whose_proof_never_got_logged_is_not_left_waiting_after_a_restart(self):
        c, _ = controls()
        c.act("compact", "ios", "", [row()])
        restarted = Controls(FakePanes(False), FixedClock(NOW + 20 * 60), lambda line: None, c.action_log)
        self.assertEqual("not_seen", restarted.today()["rows"][0]["state"])

    def test_a_restart_keeps_waiting_for_a_proof_and_matches_it(self):
        c, _ = controls()
        c.act("compact", "ios", "", [row()])
        restarted = Controls(FakePanes(False), FixedClock(NOW + 60), lambda line: None, c.action_log)
        proof = replace(stats(60_000), compactions=[Compaction(NOW + 40, "manual", 400_000, 60_000, None, None)])
        self.assertEqual("done", restarted.effects([row()], {"s1": proof}, NOW + 60)[0]["state"])
        self.assertEqual("done", restarted.today()["rows"][0]["state"])

    def test_a_restart_while_typing_holds_the_session_so_the_control_is_never_sent_twice(self):
        log = FakeActionLog()
        c, _ = controls()
        c.action_log = log

        class StopsWhileTyping(FakePanes):
            def type_into(self, pane, text):
                raise SystemExit  # the cockpit restarts between the log line and the typing

        c.panes = StopsWhileTyping()
        with self.assertRaises(SystemExit):
            c.send(row(), "compact", "/compact", "", "autopilot", "over its sweet spot")
        self.assertEqual(["typing"], [r["event"] for r in log.records])
        self.assertEqual({"ios"}, Controls(FakePanes(), FixedClock(NOW + 5), lambda line: None, log).pending())

    def test_a_pane_that_refuses_the_text_ends_its_typing_line(self):
        c, _ = controls(fails=True)
        self.assertFalse(c.send(row(), "compact", "/compact", "", "autopilot", "")["ok"])
        self.assertEqual(["typing", "not_typed"], [r["event"] for r in c.action_log.records])
        self.assertEqual(set(), Controls(FakePanes(), FixedClock(NOW + 5), lambda line: None, c.action_log).pending())

    def test_no_compact_or_clear_while_its_pane_shows_background_work(self):
        self.assertIsNone(command_for("compact", row(background="1 shell"))[0])
        self.assertIsNone(command_for("clear", row(background="2 local agents"))[0])
        self.assertEqual("/effort medium", command_for("effort", row(background="1 shell"), "medium")[0])

    def test_a_model_or_effort_row_waits_for_its_turn_even_if_the_old_rule_logged_no_proof(self):
        log = FakeActionLog()
        for id, kind in (("a1", "model"), ("a2", "effort")):
            log.append({"t": NOW - 3600, "id": id, "event": "sent", "origin": "autopilot", "session": "ios", "kind": kind, "text": f"/{kind} x"})
        log.append({"t": NOW - 2700, "id": "a1", "event": "not_seen", "origin": "autopilot", "text": "No proof in its transcript after 15 min"})
        log.append({"t": NOW - 60, "id": "a3", "event": "sent", "origin": "autopilot", "session": "ios", "kind": "model",
                    "text": "/model claude-sonnet-5-5", "level": "claude-sonnet-5-5"})
        rows = day_rows(log.since(0), "autopilot", NOW)
        self.assertEqual(["waiting", "waiting", "waiting"], [r["state"] for r in rows])
        self.assertEqual("Waiting for its next turn on claude-sonnet-5-5.", rows[0]["result"])

    def test_a_control_is_typed_into_the_pane_and_waits_for_its_proof(self):
        c, panes = controls()
        self.assertTrue(c.act("compact", "ios", "", [row()])["ok"])
        self.assertEqual([("w1:p2", "/compact")], panes.typed)
        self.assertEqual("waiting", c.effects([row()], {}, NOW)[0]["state"])

    def test_a_refused_or_failed_control_types_nothing_and_says_why(self):
        c, panes = controls()
        self.assertFalse(c.act("clear", "ios", "", [row(holds=1)])["ok"])
        self.assertFalse(c.act("compact", "nobody", "", [row()])["ok"])
        self.assertEqual([], panes.typed)
        failing, _ = controls(fails=True)
        self.assertIn("no such pane", failing.act("compact", "ios", "", [row()])["error"])
        self.assertEqual([], failing.effects([row()], {}, NOW))

    def test_compact_is_done_on_its_compact_boundary_record(self):
        c, _ = controls()
        c.act("compact", "ios", "", [row()])
        after = replace(stats(60_000), compactions=[Compaction(NOW + 30, "manual", 400_000, 60_000, None, None)])
        result = c.effects([row()], {"s1": after}, NOW + 60)[0]
        self.assertEqual("done", result["state"])
        self.assertIn("400k to 60k", result["text"])

    def test_clear_is_done_on_a_new_session_and_effort_on_the_next_turn(self):
        c, _ = controls()
        c.act("clear", "ios", "", [row()])
        c.act("effort", "ios", "medium", [row()])
        later = replace(stats(20_000, effort="medium"), last_turn_at=NOW + 10)
        effects = {e["kind"]: e for e in c.effects([row(session_id="s2", context=20_000)], {"s2": later}, NOW + 60)}
        self.assertEqual(("done", "done"), (effects["clear"]["state"], effects["effort"]["state"]))
        self.assertIn("new session s2", effects["clear"]["text"])

    def test_no_proof_in_15_minutes_is_not_seen(self):
        c, _ = controls()
        c.act("compact", "ios", "", [row()])
        self.assertEqual("not_seen", c.effects([row()], {"s1": stats(400_000)}, NOW + 16 * 60)[0]["state"])

    def test_an_effort_on_an_idle_session_waits_for_its_next_turn_without_holding_it(self):
        c, _ = controls()
        c.act("effort", "ios", "medium", [row()])
        self.assertEqual("waiting", c.effects([row()], {"s1": stats(400_000)}, NOW + 3 * 3600)[0]["state"])
        self.assertEqual(set(), c.pending())


if __name__ == "__main__":
    unittest.main()


class NeedSendTest(unittest.TestCase):
    def app(self, rows, needs):
        from cockpit.server.cockpit_app import CockpitApp
        ctl, panes = controls()
        app = CockpitApp(None, None, ctl, None, 30, lambda line: None, None, None)
        app.snapshot = {"sessions": rows, "needs": needs}
        return app, panes, ctl

    def test_a_needs_prompt_types_the_cores_own_text_and_waits_for_the_next_turn(self):
        need = {"id": "off-agent-ai", "action_kind": "send", "action_payload": "coordinator: set pg-x back to open", "target": "coordinator",
                "text": "agent-ai works off the milestone"}
        app, panes, ctl = self.app([row(name="coordinator", pane="w1:p9")], [need])
        self.assertTrue(app.act({"kind": "need", "session": "off-agent-ai"})["ok"])
        self.assertEqual([("w1:p9", "coordinator: set pg-x back to open")], panes.typed)
        effect = ctl.effects([row(name="coordinator")], {"s1": stats(100_000, last_turn=NOW + 60)}, NOW + 90)
        self.assertEqual("done", effect[0]["state"])

    def test_an_unknown_or_copy_only_row_types_nothing(self):
        need = {"id": "login-2", "action_kind": "copy", "action_payload": "cswap-relogin 2", "target": "", "text": "x"}
        app, panes, _ = self.app([row()], [need])
        self.assertFalse(app.act({"kind": "need", "session": "login-2"})["ok"])
        self.assertFalse(app.act({"kind": "need", "session": "nothing"})["ok"])
        self.assertEqual([], panes.typed)

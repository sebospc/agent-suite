import unittest
from dataclasses import replace

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.autopilot.autopilot import Autopilot
from cockpit.autopilot.rules import compaction_line, decide, skipped, thrashing
from cockpit.autopilot.window_step import window_commands
from cockpit.clock.fixed_clock import FixedClock
from cockpit.compaction.recovery_mix import RecoveryMix
from cockpit.controls.controls import Controls
from cockpit.live_sessions.live_session import LiveSession
from cockpit.panes.fake_panes import FakePanes
from cockpit.sessions.session_row import session_row
from cockpit.transcripts.session_stats import Compaction
from tests.builders import NOW, prices, thresholds
from tests.test_autopilot import row
from tests.test_sessions import stats


class ThrashGuardTest(unittest.TestCase):
    def test_two_compactions_in_a_row_that_refill_to_its_sweet_spot_stop_the_autopilot_compacting_it(self):
        thrashing = row(refills=[290_000, 300_000])
        self.assertEqual([], decide([thrashing], set(), thresholds(), NOW))
        why = skipped([thrashing], set(), thresholds(), NOW)[0]["why"]
        self.assertTrue(why.startswith("thrash guard: its last two compactions each left it at 290k, 300k"), why)

    def test_one_refill_or_a_compaction_that_freed_it_does_not_stop_it(self):
        for refills in ([300_000], [120_000, 300_000], [300_000, 120_000]):
            self.assertEqual(1, len(decide([row(refills=refills)], set(), thresholds(), NOW)), refills)

    def test_a_thrashing_haiku_session_is_judged_against_the_guard_line(self):
        # The line a TASK's compaction is judged against; the guard rule itself is gone (panels f68cd6 to b31e2b).
        haiku = row(name="coordinator", model="Haiku 5.5", haiku_guarded=True, context=96_000, over=False, refills=[95_000, 97_000])
        guard = 90_000
        self.assertEqual(guard, compaction_line(haiku, guard))
        self.assertTrue(thrashing(haiku, compaction_line(haiku, guard)))
        self.assertFalse(thrashing(dict(haiku, refills=[40_000, 97_000]), guard))

    def test_a_clear_when_a_task_arrives_is_still_sent(self):
        suggested = {"bead": "pg-a1", "next": True, "needs_history": False, "model": "Opus 5.5", "model_id": "", "effort": "",
                     "next_folders": ["/repo/ios"], "done_folders": ["/repo/web"]}
        thrashing = row(refills=[290_000, 300_000], holds=0, kind="found", suggested=suggested, notes_saved=True, cache_ttl=3600,
                        last_turn_at=NOW - 7200)
        task = {"ios": {"id": "t1", "bead": "pg-a1"}}
        self.assertEqual(["clear"], [c["kind"] for c in decide([thrashing], set(), thresholds(), NOW, task)])
        compact = dict(thrashing, suggested=dict(suggested, needs_history=True))
        self.assertEqual(["keep"], [c["kind"] for c in decide([compact], set(), thresholds(), NOW, task)])


def live(name, model_id, state="idle", pane=None, account="1"):
    return {"name": name, "model_id": model_id, "state": state, "pane": f"p-{name}" if pane is None else pane, "account": account,
            "context": 100_000, "effort": "high", "session_id": f"s-{name}", "over": False, "spot": None, "notes_saved": True,
            "holds": 0, "kind": "found", "last_turn_at": NOW - 60, "cache_ttl": 3600}


TEAM = [live("brain", "claude-opus-5-5", "busy"), live("ios", "claude-opus-5-5"), live("android", "claude-opus-5-5[1m]"),
        live("coordinator", "claude-haiku-5-5"), live("design", "claude-sonnet-5-5", "busy"), live("format", "claude-fable-5-1"),
        live("backend", "claude-sonnet-5-5", "off"), live("ai", "claude-opus-5-5", "busy", account="2")]


def window_texts(panes):
    return [t for _, t in panes.typed if t.startswith("/autocompact")]


class WindowStepTest(unittest.TestCase):
    def test_once_per_model_per_account_into_an_idle_session_first(self):
        self.assertEqual([("format", "1", "/autocompact 1000000"), ("android", "1", "/autocompact 1000000"),
                          ("design", "1", "/autocompact 1000000"), ("ai", "2", "/autocompact 1000000")],
                         [(c["session"], c["account"], c["text"]) for c in window_commands(True, TEAM, {})])
        self.assertEqual([], window_commands(False, TEAM, {}))  # never set is Claude Code's 200k already
        self.assertEqual(["/autocompact 200000"] * 4,
                         [c["text"] for c in window_commands(False, TEAM, {("1", "claude-opus-5-5"): "on", ("1", "claude-sonnet-5-5"): "on",
                                                                          ("1", "claude-fable-5-1"): "on", ("2", "claude-opus-5-5"): "on"})])
        self.assertEqual([], window_commands(True, [live("coordinator", "claude-haiku-5-5")], {}))

    def pilot(self, on=True, log=None, panes=None):
        log, panes = log or FakeActionLog(), panes or FakePanes()
        controls = Controls(panes, FixedClock(NOW), lambda line: None, log)
        return Autopilot(controls, thresholds(autopilot_on=on), log, FixedClock(NOW), lambda line: None), panes, log

    def test_nothing_is_typed_while_paused_and_the_step_runs_once_the_pause_lifts(self):
        pilot, panes, log = self.pilot()
        pilot.step(TEAM, paused=True)
        pilot.step(TEAM, paused=True)
        self.assertEqual([], panes.typed)
        self.assertEqual(["held"], [r["event"] for r in log.records])
        pilot.step([r for r in TEAM if r["name"] != "brain"], paused=False)
        self.assertEqual(4, window_texts(panes).count("/autocompact 1000000"))
        pilot.step(TEAM, paused=False)
        self.assertEqual(4, len(window_texts(panes)))  # once per switch

    def test_an_account_that_shows_up_later_gets_the_step_then(self):
        pilot, panes, _ = self.pilot()
        pilot.step(TEAM[:-1])
        self.assertEqual(3, len(window_texts(panes)))
        pilot.step(TEAM + [live("web", "claude-opus-5-5", account="2")])
        self.assertEqual([("p-web", "/autocompact 1000000")], [(p, t) for p, t in panes.typed if t.startswith("/autocompact")][3:])

    def test_a_restart_remembers_what_each_account_got_and_turning_off_sets_200k(self):
        _, _, log = self.pilot()
        first, _, _ = self.pilot(log=log)
        first.step(TEAM)
        again, panes, _ = self.pilot(log=log)
        again.step(TEAM)
        self.assertEqual([], window_texts(panes))
        off, panes, _ = self.pilot(on=False, log=log)
        off.step(TEAM)
        self.assertEqual(["/autocompact 200000"] * 4, [t for _, t in panes.typed])

    def test_a_pane_that_refuses_it_is_held_and_the_next_session_of_that_pair_is_tried(self):
        pilot, _, _ = self.pilot(panes=FakePanes(fails=True))
        pilot.step(TEAM)
        self.assertEqual({"format", "android", "design", "ai"}, set(pilot.unreachable))
        pilot.step(TEAM)
        self.assertEqual({"ios"}, set(pilot.unreachable) - {"format", "android", "design", "ai"})
        pilot.step(TEAM)
        self.assertEqual(6, len(pilot.unreachable))  # brain, the last Opus session on account 1

    def test_only_a_compaction_proves_it_never_the_settings_file_alone(self):
        pilot, _, log = self.pilot()
        pilot.step(TEAM)
        self.assertEqual(set(), pilot.controls.pending())
        saved = dict(TEAM[2], auto_compact_window=1_000_000)  # saved, but a project file can still override it (F11)
        self.assertEqual(["waiting"], [e["state"] for e in pilot.controls.effects([saved], {}, NOW + 10) if e["session"] == "android"])
        proved = replace(stats(60_000), compactions=[Compaction(NOW + 60, "manual", 150_000, 40_000, None, None),
                                                     Compaction(NOW + 90, "manual", 285_000, 60_000, None, None)])
        self.assertEqual(["done"], [e["state"] for e in pilot.controls.effects([saved], {"s-android": proved}, NOW + 100)
                                    if e["session"] == "android"])
        self.assertEqual(["done"], [r["event"] for r in log.records if r.get("session") == "android" and r["event"] not in ("typing", "sent")])

    def test_an_auto_compaction_far_below_the_window_refutes_it(self):
        for pre in (167_000, 267_000):  # the 200k default, and the 300k project override of brain's report F11
            pilot, _, log = self.pilot()
            pilot.step(TEAM)
            refuted = replace(stats(60_000), compactions=[Compaction(NOW + 60, "auto", pre, 40_000, None, None)])
            self.assertEqual(["failed"], [e["state"] for e in pilot.controls.effects([TEAM[2]], {"s-android": refuted}, NOW + 99_999)
                                          if e["session"] == "android"])

    def test_haiku_gets_its_sweet_spot_window_and_is_retyped_when_it_changes(self):
        coordinator = dict(live("coordinator", "claude-haiku-5-5"), window=128_000)
        self.assertEqual(["/autocompact 128000"], [c["text"] for c in window_commands(True, [coordinator], {})])
        self.assertEqual([], window_commands(True, [coordinator], {("1", "claude-haiku-5-5"): "128000"}))
        # The 125k the 5k round-down typed compacts 3k under its spot, so the new window goes out.
        self.assertEqual(["/autocompact 128000"], [c["text"] for c in window_commands(True, [coordinator], {("1", "claude-haiku-5-5"): "125000"})])
        self.assertEqual(["/autocompact 128000"], [c["text"] for c in window_commands(False, [coordinator], {("1", "claude-haiku-5-5"): "115000"})])
        self.assertEqual([], window_commands(True, [dict(coordinator, window=None)], {}))  # no sweet spot yet: left alone
        self.assertEqual(["/autocompact 100000"], [c["text"] for c in window_commands(True, [dict(coordinator, window=60_000)], {})])
        auto = replace(stats(30_000), compactions=[Compaction(NOW + 60, "auto", 97_000, 30_000, None, None)])
        pilot, _, _ = self.pilot()
        pilot.step([coordinator])
        self.assertEqual(["done"], [e["state"] for e in pilot.controls.effects([coordinator], {"s-coordinator": auto}, NOW + 100)])


class HowItIsWorkedOutTest(unittest.TestCase):
    def test_the_panel_shows_the_task_kind_and_its_measured_recovery(self):
        live_session = LiveSession("agent-ios", "s1", 1, "w1:p2", "15", "idle")
        work = {"bead": "pg-c1", "tag": "", "kind": "dod", "line": "", "held": []}
        mix = RecoveryMix(fresh=0, write=20_000, read=900_000, out=4_000, compactions=7, kind="ios", provisional=False)
        found = session_row("ios", live_session, stats(200_000), work, [], None, [], thresholds(), prices(), NOW,
                            recovery=mix, task_kind="ios", kind_source="labels of pg-c1")
        lines = {i["name"]: i["value"] for i in found["inputs"]}
        self.assertEqual("ios, from labels of pg-c1", lines["Task kind"])
        self.assertRegex(lines["R, recovery after a compaction"], r"^\d+k tokens, \$\d\.\d\d at list price; mean of its kind's last 7")
        fleet = session_row("ios", live_session, stats(200_000), work, [], None, [], thresholds(), prices(), NOW,
                            recovery=replace(mix, kind="fleet", provisional=True), task_kind="docs", kind_source="labels of pg-c1")
        self.assertIn("provisional", {i["name"]: i["value"] for i in fleet["inputs"]}["R, recovery after a compaction"])
        self.assertEqual("provisional", fleet["spot_kind"])


if __name__ == "__main__":
    unittest.main()

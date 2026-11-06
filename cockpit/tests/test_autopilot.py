import unittest
from dataclasses import replace

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.autopilot.autopilot import UNREACHABLE_HOLD_S, Autopilot
from cockpit.autopilot.rules import SPOT, compaction_starts, decide, skipped
from cockpit.autopilot.turn_end import TURN_END
from cockpit.clock.fixed_clock import FixedClock
from cockpit.controls.controls import Controls
from cockpit.panes.fake_panes import FakePanes
from cockpit.transcripts.session_stats import Compaction
from tests.builders import NOW, thresholds
from tests.test_sessions import stats


def row(**fields):
    base = {"name": "ios", "state": "idle", "pane": "w1:p2", "model": "Opus 5.5", "context": 400_000, "spot": 280_000,
            "over": True, "notes_saved": True, "holds": 1, "last_turn_at": NOW - 15 * 60, "effort": "high", "session_id": "s1",
            "can_compact": True, "why": ""}
    base.update(fields)
    return base


def pilot(**overrides):
    log, panes = FakeActionLog(), FakePanes()
    controls = Controls(panes, FixedClock(NOW), lambda line: None, log)
    return Autopilot(controls, thresholds(**{"autopilot_on": True, **overrides}), log, FixedClock(NOW), lambda line: None), controls, panes


class RulesTest(unittest.TestCase):
    def test_a_session_whose_pane_shows_background_work_is_neither_compacted_nor_cleared(self):
        busy_behind = row(background="1 shell")
        self.assertEqual([], decide([busy_behind], set(), thresholds(), NOW))
        self.assertEqual([], decide([dict(busy_behind, holds=0)], set(), thresholds(), NOW, finished={"ios": "mb-1"}))
        self.assertIn("1 shell running", skipped([busy_behind], set(), thresholds(), NOW)[0]["why"])

    def test_an_idle_session_over_its_sweet_spot_for_10_minutes_is_compacted(self):
        self.assertEqual([SPOT], [c["rule"] for c in decide([row()], set(), thresholds(), NOW)])
        # 5 minutes after its turn it is still in the turn-end window, so that rule compacts it, not the 10-minute wait.
        self.assertEqual([TURN_END], [c["rule"] for c in decide([row(last_turn_at=NOW - 5 * 60)], set(), thresholds(), NOW)])
        haiku = row(model="Haiku 5.5", model_id="claude-haiku-5-5", last_turn_at=NOW - 5 * 60)
        self.assertEqual([], decide([haiku], set(), thresholds(), NOW))
        self.assertEqual([], decide([row(state="busy")], set(), thresholds(), NOW))
        self.assertEqual([], decide([row(over=False)], set(), thresholds(), NOW))

    def test_unsaved_notes_do_not_hold_the_compaction_before_expiry_and_a_waiting_control_does(self):
        # Brain, pg-o1sq finding 3 answer: waiting for saved notes is how a session goes cold at full size.
        self.assertEqual(1, len(decide([row(notes_saved=False)], set(), thresholds(), NOW)))
        self.assertEqual(1, len(decide([row(notes_saved=None, holds=1)], set(), thresholds(), NOW)))
        self.assertEqual([], decide([row()], {"ios"}, thresholds(), NOW))

    def test_a_haiku_session_at_90k_is_left_to_claude_codes_own_window(self):
        # The guard rule is gone (panels f68cd6 to b31e2b): its compactions refilled within minutes, every 3 minutes.
        haiku = row(name="coordinator", model="Haiku 5.5", haiku_guarded=True, context=91_000, over=False, last_turn_at=NOW - 30)
        self.assertEqual([], decide([haiku], set(), thresholds(), NOW))
        self.assertEqual([], skipped([haiku], set(), thresholds(), NOW))


class AutopilotTest(unittest.TestCase):
    def test_it_types_compact_logs_it_and_never_sends_twice_while_waiting(self):
        autopilot, controls, panes = pilot()
        self.assertEqual(1, autopilot.step([row()]))
        self.assertEqual(0, autopilot.step([row()]))
        self.assertEqual([("w1:p2", "/compact")], panes.typed)
        typing, sent = autopilot.action_log.records[:2]
        self.assertEqual(("typing", "sent", typing["id"]), (typing["event"], sent["event"], sent["id"]))  # logged before typed
        self.assertEqual(("sent", "autopilot", 400_000), (sent["event"], sent["origin"], sent["before_context"]))
        self.assertEqual("waiting", autopilot.today()["rows"][0]["state"])

    def test_today_counts_the_context_its_proved_compactions_cut(self):
        autopilot, controls, _ = pilot()
        autopilot.step([row()])
        after = replace(stats(60_000), compactions=[Compaction(NOW + 5, "manual", 400_000, 60_000, None, None)])
        controls.effects([row()], {"s1": after}, NOW + 10)
        today = autopilot.today()
        self.assertEqual(("done", 340_000, 1), (today["rows"][0]["state"], today["cut"], today["done"]))
        self.assertEqual(set(), controls.pending())

    def test_it_does_nothing_when_turned_off(self):
        autopilot, _, panes = pilot(autopilot_on=False)
        self.assertEqual(0, autopilot.step([row()]))
        self.assertEqual([], panes.typed)


if __name__ == "__main__":
    unittest.main()


TASK = {"id": "t1", "bead": "pg-a1"}


class JevRulesTest(unittest.TestCase):
    def row(self, **fields):
        base = {"name": "ios", "state": "idle", "pane": "w1:p2", "model": "Opus 5.5", "effort": "high", "context": 80_000,
                "over": False, "notes_saved": True, "holds": 1, "kind": "dod", "last_turn_at": NOW - 120, "cache_ttl": 3600,
                "suggested": {"bead": "pg-a1", "model": "Opus 5.5", "model_id": "claude-opus-5-5", "effort": "medium",
                              "next": False, "needs_history": False}}
        base.update(fields)
        return base

    def test_a_session_whose_transcript_is_not_read_yet_gets_nothing(self):
        unread = self.row(context=None, last_turn_at=None, effort="", holds=0, notes_saved=None,
                          suggested=dict(self.row()["suggested"], model="Sonnet 5.5", model_id="claude-sonnet-5-5"))
        self.assertEqual([], decide([unread], set(), thresholds(), NOW))

    def test_unsaved_notes_block_a_clear(self):
        # Brain, pg-o1sq finding 3 answer: unsaved notes block a clear only; a compaction's summary keeps the work.
        cold = dict(self.arrives(), notes_saved=False)
        under = decide([dict(cold, context=30_000)], set(), thresholds(), NOW, {"ios": TASK})[0]
        self.assertEqual("keep", under["kind"])
        self.assertIn("kept instead: its notes were not saved", under["reason"])
        over = decide([cold], set(), thresholds(), NOW, {"ios": TASK})[0]
        self.assertEqual(("compact", "/compact"), (over["kind"], over["text"]))
        self.assertIn("compacted instead of cleared", over["reason"])
        related = dict(cold, suggested=dict(cold["suggested"], related=True))
        self.assertEqual("compact", decide([related], set(), thresholds(), NOW, {"ios": TASK})[0]["kind"])

    def arrives(self, **fields):
        """Idle 2 h on a 1 h cache, holding no bead, with Jev's fresh-start verdict on the TASK's bead."""
        base = dict(self.row(holds=0, kind="idle", last_turn_at=NOW - 7200, spot=60_000),
                    suggested=dict(self.row()["suggested"], next=True, bead="pg-a1", next_folders=["/repo/ios"], done_folders=["/repo/web"]))
        base.update(fields)
        return base

    def kind(self, row, **thresholds_overrides):
        return decide([row], set(), thresholds(**thresholds_overrides), NOW, {"ios": TASK})[0]["kind"]

    def test_nothing_happens_at_a_task_end_only_when_a_task_arrives(self):
        self.assertEqual([], decide([self.arrives()], set(), thresholds(), NOW))
        self.assertEqual(("clear", "/clear", 3, "t1", "pg-a1"),
                         tuple(decide([self.arrives()], set(), thresholds(), NOW, {"ios": TASK})[0][k]
                               for k in ("kind", "text", "case", "task", "bead")))

    def test_a_warm_cache_follows_the_sweet_spot(self):
        warm = self.arrives(last_turn_at=NOW - 600, suggested=dict(self.arrives()["suggested"], related=True))
        self.assertEqual("compact", self.kind(warm))                      # 80k over its 60k sweet spot, related work
        self.assertEqual("clear", self.kind(self.arrives(last_turn_at=NOW - 600)))  # unrelated, other folders: nothing to summarise
        self.assertEqual("compact", self.kind(self.arrives(last_turn_at=NOW - 600, holds=1)))
        self.assertEqual("keep", self.kind(dict(warm, context=40_000)))   # under it: its cache is kept as it is
        self.assertEqual("keep", self.kind(dict(warm, cache_ttl=None, last_turn_at=NOW - 7200, spot=None)))  # unknown life is warm

    def test_a_cold_cache_keeps_related_work_and_clears_the_rest(self):
        cold = self.arrives()
        related = dict(cold, suggested=dict(cold["suggested"], related=True))
        small = dict(related, context=30_000)
        self.assertEqual((2, "keep"), tuple(decide([small], set(), thresholds(), NOW, {"ios": TASK})[0][k] for k in ("case", "kind")))
        history = dict(cold, suggested=dict(cold["suggested"], needs_history=True))
        self.assertEqual("compact", self.kind(history))
        self.assertEqual("keep", self.kind(dict(history, context=30_000)))  # small enough to read once in full
        self.assertEqual("keep", self.kind(dict(cold, holds=1, context=30_000)))  # Q8 row 7: never cleared
        self.assertEqual("keep", self.kind(dict(cold, kind="role", context=30_000)))
        other_bead = decide([dict(cold, context=30_000)], set(), thresholds(), NOW, {"ios": dict(TASK, bead="pg-zz")})[0]  # Jev judged another bead
        self.assertEqual("keep", other_bead["kind"])

    def test_cold_and_over_its_line_it_compacts_if_related_and_clears_if_not_never_keeps(self):
        # Brain, pg-o1sq relaunch HOLD finding 3: a 397k session sat cold over its line, kept.
        cold = self.arrives()
        related = dict(cold, suggested=dict(cold["suggested"], related=True))
        self.assertEqual((2, "compact"), tuple(decide([related], set(), thresholds(), NOW, {"ios": TASK})[0][k] for k in ("case", "kind")))
        self.assertEqual((7, "compact"), tuple(decide([dict(cold, holds=1)], set(), thresholds(), NOW, {"ios": TASK})[0][k] for k in ("case", "kind")))
        self.assertEqual("compact", self.kind(dict(cold, kind="role")))
        self.assertEqual("compact", decide([cold], set(), thresholds(), NOW, {"ios": dict(TASK, bead="pg-zz")})[0]["kind"])  # no verdict
        self.assertEqual((3, "clear"), tuple(decide([cold], set(), thresholds(), NOW, {"ios": TASK})[0][k] for k in ("case", "kind")))

    def test_a_cold_clear_still_needs_other_folders(self):
        same = self.arrives(task_files=["/repo/web/a.py"], suggested=dict(self.arrives()["suggested"], next_folders=["/repo/web"]))
        choice = decide([dict(same, context=30_000)], set(), thresholds(), NOW, {"ios": TASK})[0]
        self.assertEqual("keep", choice["kind"])
        self.assertIn("touches the folders of", choice["reason"])
        self.assertEqual("compact", decide([same], set(), thresholds(), NOW, {"ios": TASK})[0]["kind"])  # over its line
        self.assertEqual("keep", decide([dict(self.arrives(), context=30_000)], set(), thresholds(), NOW, {"ios": TASK}, only_compact={"ios"})[0]["kind"])

    def test_with_no_task_it_compacts_just_before_its_cache_expires(self):
        over = self.row(over=True, spot=60_000, holds=1)
        self.assertEqual([], decide([dict(over, last_turn_at=NOW - 15 * 60)], set(), thresholds(), NOW))
        self.assertEqual([SPOT], [c["rule"] for c in decide([dict(over, last_turn_at=NOW - 56 * 60)], set(), thresholds(), NOW)])
        self.assertEqual([], decide([dict(over, last_turn_at=NOW - 61 * 60)], set(), thresholds(), NOW))  # cold: its next TASK decides
        self.assertEqual(1, len(decide([dict(over, cache_ttl=300, last_turn_at=NOW - 160)], set(), thresholds(), NOW)))
        whys = [s["why"] for s in skipped([dict(over, last_turn_at=NOW - 15 * 60)], set(), thresholds(), NOW) if s["rule"] == SPOT]
        self.assertEqual(["idle 15 m; it compacts at 55 m, just before its 60 m cache expires, unless a TASK comes first"], whys)


    def test_the_window_opens_earlier_by_the_last_read_gap(self):
        # Brain, pg-o1sq relaunch HOLD finding 2: reads 17 m apart skipped the 55 to 60 m window of a 397k session.
        over = dict(self.row(over=True, spot=60_000, holds=1), last_turn_at=NOW - 40 * 60)
        self.assertEqual([], decide([over], set(), thresholds(), NOW))
        self.assertEqual([SPOT], [c["rule"] for c in decide([over], set(), thresholds(), NOW, read_gap=17 * 60)])
        self.assertEqual([], decide([dict(over, last_turn_at=NOW - 61 * 60)], set(), thresholds(), NOW, read_gap=17 * 60))
        whys = [s["why"] for s in skipped([dict(over, last_turn_at=NOW - 15 * 60)], set(), thresholds(), NOW, 17 * 60) if s["rule"] == SPOT]
        self.assertEqual(["idle 15 m; it compacts at 38 m, just before its 60 m cache expires, unless a TASK comes first"], whys)

    def test_the_autopilot_measures_its_read_gap_between_steps(self):
        autopilot, _, panes = pilot()
        over = row(over=True, spot=60_000, holds=1, cache_ttl=3600, last_turn_at=NOW - 40 * 60)
        self.assertEqual(0, autopilot.step([over]))  # first read: no gap known
        autopilot.last_step_at = NOW - 17 * 60
        self.assertEqual(1, autopilot.step([over]))

    def test_a_busy_session_over_its_ceiling_compacts_once_its_turn_ends(self):
        # pg-45v5 ruling: cockpit sat at 420k of a 154k spot, always busy, so the expiry window never came.
        from cockpit.autopilot.rules import CEILING
        over = dict(self.row(over=True, spot=154_000, holds=1), context=420_000, ceiling=250_000, last_turn_at=NOW - 20)
        self.assertEqual([], [c for c in decide([dict(over, state="busy")], set(), thresholds(), NOW) if c["kind"] == "compact"])
        self.assertEqual([CEILING], [c["rule"] for c in decide([over], set(), thresholds(), NOW) if c["kind"] == "compact"])
        # Under the ceiling the turn line compacts it; the ceiling stays as the backstop (panels f68cd6 to b31e2b).
        self.assertEqual([TURN_END], [c["rule"] for c in decide([dict(over, context=240_000)], set(), thresholds(), NOW) if c["kind"] == "compact"])

class WrongClearTest(unittest.TestCase):
    def test_a_clear_whose_next_session_reads_the_old_files_is_wrong_and_two_stop_clears(self):
        autopilot, controls, panes = pilot()
        log = autopilot.action_log
        suggested = {"bead": "pg-b2", "model": "Opus 5.5", "model_id": "", "effort": "", "next": True, "needs_history": False,
                     "next_folders": ["/repo/ios"], "done_folders": ["/repo/web"]}
        done = row(holds=0, kind="idle", over=False, suggested=suggested, task_files=["/repo/web/a.py"], cache_ttl=3600,
                   last_turn_at=NOW - 7200)
        self.assertEqual(1, autopilot.step([done], arriving={"ios": {"id": "t1", "bead": "pg-b2"}}))
        self.assertEqual(0, autopilot.step([done], arriving={"ios": {"id": "t1", "bead": "pg-b2"}}))  # one decision per TASK
        cleared = [r for r in log.records if r["event"] == "cleared"]
        self.assertEqual([["/repo/web/a.py"]], [r["files"] for r in cleared])
        fresh = dict(done, session_id="s2", started_at=NOW + 1, first_reads=["/repo/web/a.py"], suggested=None)
        self.assertEqual({"ios": 1}, autopilot.judge_clears([fresh], NOW + 60))
        self.assertEqual({"ios": 1}, autopilot.judge_clears([fresh], NOW + 120))  # logged once
        log.append(dict(cleared[0], id="other"))
        self.assertEqual({"ios": 2}, autopilot.judge_clears([fresh], NOW + 180))
        self.assertEqual([{"session": "ios", "clears": 2, "wrong": 2, "right": 0, "compacts_right": 0, "compacts_wrong": 0, "only_compact": True}], autopilot.clears_of_week(NOW + 180))


class TaskStartTest(unittest.TestCase):
    def test_each_task_is_decided_once_logged_and_remembered_across_a_restart(self):
        autopilot, controls, panes = pilot()
        warm = row(over=False, holds=0, kind="idle", spot=500_000, cache_ttl=3600, last_turn_at=NOW - 600)
        arriving = {"ios": {"id": "t9", "bead": "pg-a1"}}
        self.assertEqual(0, autopilot.step([warm], arriving=arriving))  # keep: nothing typed
        self.assertEqual([], panes.typed)
        starts = [r for r in autopilot.action_log.records if r["event"] == "task_start"]
        self.assertEqual([("t9", "keep", 1)], [(r["task"], r["action"], r["case"]) for r in starts])
        over = dict(warm, context=600_000)
        self.assertEqual(0, autopilot.step([over], arriving=arriving))  # already decided
        restarted = Autopilot(controls, autopilot.thresholds, autopilot.action_log, FixedClock(NOW), lambda line: None)
        self.assertEqual(0, restarted.step([over], arriving=arriving))
        self.assertEqual(1, restarted.step([over], arriving={"ios": {"id": "t10", "bead": "pg-a1"}}))
        self.assertEqual([("w1:p2", "/compact")], panes.typed)


class SkipLogTest(unittest.TestCase):
    def test_a_skip_is_logged_once_when_its_reason_starts(self):
        log = FakeActionLog()
        controls = Controls(FakePanes(), FixedClock(NOW), lambda line: None, log)
        pilot = Autopilot(controls, thresholds(autopilot_on=True), log, FixedClock(NOW), lambda line: None)
        busy = {"name": "ios", "state": "busy", "pane": "w1:p2", "model": "Opus 5.5", "effort": "high", "context": 400_000,
                "over": True, "spot": 200_000, "notes_saved": True, "holds": 1, "kind": "dod", "last_turn_at": NOW - 60, "cache_ttl": 3600}
        pilot.step([busy])
        pilot.step([busy])
        skips = [r for r in log.records if r["event"] == "skipped"]
        self.assertEqual([("ios", "busy, so it waits for the turn to end", 400_000)], [(r["session"], r["why"], r["context"]) for r in skips])


    def test_a_pane_that_refuses_the_text_is_logged_and_shown_as_a_skip_reason(self):
        log = FakeActionLog()
        controls = Controls(FakePanes(fails=True), FixedClock(NOW), lambda line: None, log)
        pilot = Autopilot(controls, thresholds(autopilot_on=True), log, FixedClock(NOW), lambda line: None)
        pilot.step([row(name="coordinator")])
        self.assertEqual(["typing", "not_typed", "refused"], [r["event"] for r in log.records if r["session"] == "coordinator"])
        pilot.step([row(name="coordinator")])
        reasons = [r["why"] for r in log.records if r["event"] == "skipped"]
        self.assertTrue(reasons and reasons[0].startswith("its pane w1:p2 refused the last text (herdr agent prompt"))


class HaikuBaseTest(unittest.TestCase):
    def test_a_haiku_session_over_the_step_and_under_its_sweet_spot_gets_no_compaction_from_the_autopilot(self):
        row = {"name": "coordinator", "state": "idle", "pane": "w1:p3", "model": "Haiku 5.5", "haiku_guarded": True, "effort": "low", "context": 122_000,
               "over": False, "notes_saved": None, "holds": 0, "kind": "role", "last_turn_at": NOW - 900, "cache_ttl": 3600,
               "base": 60_000}
        self.assertEqual([], decide([row], set(), thresholds(), NOW))


class RetryTest(unittest.TestCase):
    def pilot(self, panes):
        log = FakeActionLog()
        controls = Controls(panes, FixedClock(NOW), lambda line: None, log)
        return Autopilot(controls, thresholds(autopilot_on=True), log, FixedClock(NOW), lambda line: None), controls

    def row(self, **fields):
        base = {"name": "ai", "state": "idle", "pane": "w4:pC", "model": "Opus 5.5", "effort": "medium", "context": 9_800, "session_id": "s1",
                "over": False, "notes_saved": None, "holds": 0, "kind": "idle", "last_turn_at": NOW - 7200, "cache_ttl": 3600,
                "suggested": {"bead": "pg-a1", "model": "Sonnet 5.5", "model_id": "claude-sonnet-5-5", "effort": "medium",
                              "next": True, "needs_history": False}}
        base.update(fields)
        return base

    def test_a_pane_herdr_does_not_know_is_not_retried_on_every_read(self):
        panes = FakePanes(fails=True)
        pilot, _ = self.pilot(panes)
        lines = []
        pilot.log = lines.append
        over = self.row(context=300_000, ceiling=200_000, spot=150_000)
        pilot.step([over])
        pilot.step([over])
        self.assertEqual(1, sum("not tried again" in line for line in lines))

    def test_a_refusal_never_holds_past_the_compaction_window_of_a_warm_cache(self):
        pilot, _ = self.pilot(FakePanes(fails=True))
        warm = self.row(last_turn_at=NOW - 40 * 60, cache_ttl=3600)
        pilot.refused(warm, "compact", "its input line holds unsent text", NOW)
        self.assertEqual(warm["last_turn_at"] + compaction_starts(3600, pilot.thresholds), pilot.unreachable["ai"][1])
        self.assertLess(pilot.unreachable["ai"][1], NOW + UNREACHABLE_HOLD_S)

    def test_the_second_refusal_in_a_row_notifies_the_owner_once(self):
        panes = FakePanes(fails=True)
        pilot, _ = self.pilot(panes)
        for _ in range(3):
            pilot.refused(self.row(), "compact", "herdr agent prompt w4:pC exited 1: agent_not_found", NOW)
        self.assertEqual(1, len(panes.notified))
        self.assertIn("ai refused the autopilot twice", panes.notified[0][1])

    def test_nothing_is_typed_while_the_team_is_paused(self):
        panes = FakePanes()
        pilot, _ = self.pilot(panes)
        self.assertEqual(0, pilot.step([self.row()], paused=True))
        self.assertEqual([], panes.typed)

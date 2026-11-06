import unittest

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.refit.bounds import Range, bounded
from cockpit.refit.fitters import expiry_margin, jev_cutoff, labelled_starts, recovery_idle_gap
from cockpit.transcripts.transcript_stats import turn_gaps
from cockpit.refit.learned_light import learned_light, proposal_needs
from cockpit.refit.refitter import DAY, Refitter
from tests.builders import NOW, thresholds

MARGIN = "cache_expiry_margin_minutes"


def compactions(minutes, n=12):
    """n autopilot compactions, each proved `minutes` after it was sent."""
    log = FakeActionLog()
    for i in range(n):
        log.append({"t": NOW - 3600 * (i + 1), "event": "sent", "origin": "autopilot", "kind": "compact", "id": f"c{i}"})
        proved = NOW - 3600 * (i + 1) + minutes * 60
        log.append({"t": proved + 600, "event": "done", "origin": "autopilot", "kind": "compact", "id": f"c{i}", "proved_at": proved})
    return log


class BoundsTest(unittest.TestCase):
    def test_a_fit_moves_at_most_its_weekly_change_and_outside_its_range_changes_nothing(self):
        rng = Range(2, 15, 20)
        self.assertEqual((6.0, ""), bounded(9, 5, rng))   # 20% of 5 a week
        self.assertEqual((4.5, ""), bounded(4.5, 5, rng))
        value, why = bounded(20, 5, rng)
        self.assertIsNone(value)
        self.assertIn("outside its range 2 to 15", why)


class FitTest(unittest.TestCase):
    def test_the_margin_is_the_95th_percentile_time_to_proof_plus_one_read(self):
        self.assertEqual(3, expiry_margin(compactions(2).records, {}, 5)[0])
        self.assertIsNone(expiry_margin(compactions(2, n=5).records, {}, 5))  # too few samples
        late = [dict(r, proved_at=None) if r["event"] == "done" else r for r in compactions(2).records]
        self.assertIsNone(expiry_margin(late, {}, 5))  # a record without its boundary's time is not a sample


class RefitterTest(unittest.TestCase):
    def test_a_daily_refit_moves_within_range_logs_it_and_a_restart_keeps_it(self):
        learned, t = FakeActionLog(), thresholds()
        refit = Refitter(t, compactions(8), learned, lambda line: None, NOW)
        self.assertEqual(1, refit.step(NOW))
        self.assertEqual(6.0, t.value(MARGIN))          # fitted 9, capped at 5 + 20%
        self.assertEqual(0, refit.step(NOW + 60))        # once a day
        again = thresholds()
        restarted = Refitter(again, compactions(8), learned, lambda line: None, NOW + 120)
        self.assertEqual((6.0, 0), (again.value(MARGIN), restarted.step(NOW + 120)))
        # The weekly change counts from where the week started, not from each day's value.
        self.assertEqual(0, restarted.step(NOW + DAY + 1))
        self.assertEqual(6.0, again.value(MARGIN))

    def test_a_fit_outside_its_range_is_a_proposal_in_your_tasks(self):
        learned, t = FakeActionLog(), thresholds()
        refit = Refitter(t, compactions(30), learned, lambda line: None, NOW)
        self.assertEqual(0, refit.step(NOW))
        self.assertEqual(5, t.value(MARGIN))
        status = refit.status(NOW)
        self.assertEqual("watch", learned_light(status, NOW)["level"])
        need = proposal_needs(status)[0]
        self.assertEqual(("refit-cache_expiry_margin_minutes", "none"), (need["id"], need["action_kind"]))
        self.assertIn("outside its range", need["text"])

    def test_only_numbers_with_a_range_are_learned(self):
        names = [n["name"] for n in Refitter(thresholds(), FakeActionLog(), FakeActionLog(), lambda line: None, NOW).status(NOW)["numbers"]]
        self.assertEqual([MARGIN, "jev_yes_probability", "recovery_idle_gap_minutes"], names)


if __name__ == "__main__":
    unittest.main()


def start(i, carry_score, action, case, t=NOW - 2 * DAY):
    return {"t": t, "event": "task_start", "task": f"t{i}", "control": f"c{i}" if action != "keep" else "", "action": action,
            "case": case, "yes": 0.6, "scores": {"needs_history": 0.1, "related": carry_score, "long": 0.2}}


class CutoffTest(unittest.TestCase):
    def test_wrong_clears_above_a_score_move_the_cutoff_down_to_it(self):
        records = [start(i, 0.9, "keep", 2) for i in range(8)] + [start(10 + i, 0.2, "clear", 3) for i in range(8)]
        records += [start(20 + i, 0.5, "clear", 3) for i in range(4)]
        records += [{"event": "wrong_clear", "id": f"c{20 + i}"} for i in range(4)]  # cleared at 0.5, but it was related
        self.assertEqual(0.5, jev_cutoff(records, {"now": NOW}, 0.6)[0])
        self.assertEqual(0.6, jev_cutoff([r for r in records if r.get("event") != "wrong_clear"], {"now": NOW}, 0.6)[0])

    def test_too_few_or_unsettled_or_unrelated_starts_are_not_labels(self):
        records = [start(i, 0.9, "keep", 2) for i in range(19)]
        self.assertIsNone(jev_cutoff(records, {"now": NOW}, 0.6))
        self.assertEqual([], labelled_starts([start(1, 0.9, "keep", 2, t=NOW - 60)], NOW))  # not a day old, no mark
        self.assertEqual([], labelled_starts([start(1, 0.2, "keep", 7)], NOW))             # kept for a held bead
        self.assertEqual([(0.9, False)], labelled_starts([start(1, 0.9, "keep", 2, t=NOW - 60), {"event": "wrong", "of": "task:t1"}], NOW))



class ConfoundedTest(unittest.TestCase):
    """pg-6inz (owner b289d0 C): a decision whose model, effort, plugins or task changed inside its outcome window."""

    def starts(self):
        records = [start(i, 0.9, "keep", 2) for i in range(10)] + [start(10 + i, 0.2, "clear", 3) for i in range(10)] + \
                  [start(20 + i, 0.5, "clear", 3) for i in range(4)]
        for i, r in enumerate(records):  # one session, each window ending at the next start
            r.update(session="ios", t=NOW - 3 * DAY + i * 2 * DAY / len(records))
        return records

    def test_a_wrong_click_with_an_effort_change_in_its_window_does_not_move_the_cutoff(self):
        records = self.starts()
        wrongs = [{"event": "wrong", "of": f"task:t{20 + i}"} for i in range(4)]  # cleared at 0.5, but it was related
        self.assertEqual(0.5, jev_cutoff(records + wrongs, {"now": NOW}, 0.6)[0])
        efforts = [{"t": r["t"] + 60, "event": "sent", "kind": "effort", "session": "ios"} for r in records[20:]]
        fit = jev_cutoff(records + wrongs + efforts, {"now": NOW}, 0.6)
        self.assertEqual(0.6, fit[0])
        self.assertIn("4 confounded left out", fit[2])

    def test_a_process_restart_or_an_auto_compaction_confounds_and_the_next_start_ends_the_window(self):
        from cockpit.refit.fitters import confounding
        one = dict(start(1, 0.9, "keep", 2), session="ios", t=NOW - 2 * DAY)
        nxt = dict(start(2, 0.9, "keep", 2), session="ios", t=NOW - 2 * DAY + 600)
        restarted = {"t": NOW, "event": "process_started", "session": "ios", "at": NOW - 2 * DAY + 300}
        self.assertEqual("its process started again", confounding(one, [one, nxt, restarted]))
        auto = {"t": NOW, "event": "auto_compacted", "session": "agent-ios", "at": NOW - 2 * DAY + 300}
        self.assertEqual("Claude Code compacted it", confounding(one, [one, nxt, auto]))
        later = dict(restarted, at=NOW - 2 * DAY + 900)  # after its next TASK start: that start's window, not this one
        self.assertEqual("", confounding(one, [one, nxt, later]))

    def test_the_autopilot_logs_each_process_start_and_auto_compaction_once(self):
        from cockpit.action_log.fake_action_log import FakeActionLog
        from cockpit.autopilot.session_changes import SessionChanges
        log = FakeActionLog()
        row = {"name": "ios", "process_started_at": NOW - 600, "last_auto_compaction_at": NOW - 300}
        SessionChanges(log, NOW).step([row], NOW)
        SessionChanges(log, NOW + 30).step([row], NOW + 30)  # a restart of the cockpit: not again
        self.assertEqual(["process_started", "auto_compacted"], [r["event"] for r in log.records])

class ScoresKeptTest(unittest.TestCase):
    def test_a_task_start_keeps_jevs_scores_its_cutoff_and_its_control_id(self):
        from tests.test_autopilot import pilot, row
        autopilot, _, _ = pilot()
        suggested = {"bead": "pg-a1", "needs_history": False, "related": False, "next_folders": ["/repo/ios"], "done_folders": ["/repo/web"],
                     "bead_scores": {"needs_history": 0.1, "related": 0.2, "long": 0.3}, "scores": {"deep_reasoning": 0.9},
                     "model": "Opus 5.5", "model_id": "", "effort": ""}
        cold = row(holds=0, kind="idle", over=False, cache_ttl=3600, last_turn_at=NOW - 7200, suggested=suggested)
        autopilot.step([cold], arriving={"ios": {"id": "t1", "bead": "pg-a1"}})
        start = next(r for r in autopilot.action_log.records if r["event"] == "task_start")
        sent = next(r for r in autopilot.action_log.records if r["event"] == "sent")
        self.assertEqual(("clear", sent["id"], 0.2, 0.9, 0.6), (start["action"], start["control"], start["scores"]["related"],
                                                               start["session_scores"]["deep_reasoning"], start["yes"]))


class IdleGapTest(unittest.TestCase):
    def test_the_gap_is_the_99th_percentile_inside_a_turn_in_whole_minutes(self):
        gaps = [20.0] * 99 + [250.0]
        self.assertEqual(1, recovery_idle_gap([], {"turn_gaps": gaps}, 10)[0])
        self.assertEqual(5, recovery_idle_gap([], {"turn_gaps": [20.0] * 90 + [250.0] * 10}, 10)[0])
        self.assertIsNone(recovery_idle_gap([], {"turn_gaps": gaps[:50]}, 10))

    def test_a_gap_a_prompt_opened_is_not_inside_a_turn(self):
        rows = [{"t_first": NOW, "t_last": NOW + 5}, {"t_first": NOW + 25, "t_last": NOW + 30}, {"t_first": NOW + 900, "t_last": NOW + 905}]
        self.assertEqual((20,), turn_gaps(rows, [{"t": NOW + 899}], NOW - DAY))
        self.assertEqual((20, 870), turn_gaps(rows, [], NOW - DAY))

import unittest
from dataclasses import replace

from cockpit.autopilot.autopilot import Autopilot
from cockpit.autopilot.fake_wake_forecast import FakeWakeForecast
from cockpit.autopilot.keep_warm import KEEP_WARM, PROBE_TEXT, Stretches, probe_state, verdict
from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.clock.fixed_clock import FixedClock
from cockpit.controls.commands import COMMANDS
from cockpit.controls.controls import Controls
from cockpit.panes.fake_panes import FakePanes
from cockpit.panes.input_line import input_text
from tests.builders import NOW, thresholds
from tests.test_autopilot import row as session_row
from cockpit.classifier.fake_classifier import FakeClassifier
from cockpit.classifier.jev_wake import JevWakeForecast
from tests.test_sessions import row as built_row, stats

YES = 0.6
WARM = {"eligible": True, "cap": 3, "instead": "a cold rewrite"}


def row(**fields):
    """Idle 56 minutes on a 1 h cache, 150k against a 280k spot: inside the probe window, under its spot."""
    base = {"over": False, "context": 150_000, "last_turn_at": NOW - 56 * 60, "cache_ttl": 3600, "keep_warm": WARM, "ceiling": 400_000}
    base.update(fields)
    return session_row(**base)


def pilot(forecast, log=None, **overrides):
    log, panes = log or FakeActionLog(), FakePanes()
    controls = Controls(panes, FixedClock(NOW), lambda line: None, log)
    wake = FakeWakeForecast(forecast)
    return Autopilot(controls, thresholds(**{"autopilot_on": True, "keep_warm_probe_on": True, **overrides}), log, FixedClock(NOW),
                     lambda line: None, wake=wake), panes, wake, log


class ProbeStateTest(unittest.TestCase):
    def test_a_probe_is_due_only_in_its_window_under_the_cap_and_when_the_rule_is_on(self):
        on, off = thresholds(keep_warm_probe_on=True), thresholds(keep_warm_probe_on=False)
        self.assertEqual("due", probe_state(row(), 0, on, NOW))
        self.assertEqual("no", probe_state(row(), 0, off, NOW))                                # off until the owner turns it on
        self.assertEqual("wait", probe_state(row(last_turn_at=NOW - 20 * 60), 0, on, NOW))
        self.assertEqual("wait", probe_state(row(last_turn_at=NOW - 61 * 60), 0, on, NOW))     # past expiry it is cold
        self.assertEqual("capped", probe_state(row(), 3, on, NOW))
        self.assertEqual("no", probe_state(row(keep_warm=dict(WARM, eligible=False)), 0, on, NOW))  # over 1.75x its spot
        self.assertEqual("no", probe_state(row(context=410_000), 0, on, NOW))                  # over its ceiling: that rule compacts
        self.assertEqual("no", probe_state(row(haiku_guarded=True), 0, on, NOW))
        self.assertEqual("no", probe_state(row(state="busy"), 0, on, NOW))

    def test_no_probe_after_a_compaction_newer_than_its_last_request(self):
        # backend, 10-22: last request 15:03:54, Claude Code compacted it while idle at 15:58:31, and the probe at 15:59:52
        # wrote 50,147 tokens, the whole new context, instead of reading a warm cache.
        last_request, compacted, probed = 1792699434.0, 1792702711.0, 1792702792.0
        backend = row(name="backend", context=18_272, last_turn_at=last_request, last_compaction_at=compacted)
        on = thresholds(keep_warm_probe_on=True)
        self.assertEqual("no", probe_state(backend, 0, on, probed))
        self.assertEqual("due", probe_state(dict(backend, last_compaction_at=last_request - 600), 0, on, probed))

    def test_the_table_of_context_band_and_expected_wake(self):
        soon, hours, never = {"within_hour": .9, "never": .1}, {"within_hour": .1, "never": .1}, {"within_hour": .2, "never": .9}
        self.assertEqual("probe", verdict(row(), 0, soon, YES)["act"])
        self.assertEqual("probe", verdict(row(over=True), 0, soon, YES)["act"])
        self.assertEqual("probe", verdict(row(), 0, hours, YES)["act"])    # under its spot a probe is cheap
        self.assertEqual("leave", verdict(row(over=True), 0, hours, YES)["act"])  # over it: compacted while warm
        self.assertEqual("hold", verdict(row(over=True), 0, never, YES)["act"])
        self.assertEqual("leave", verdict(row(), 0, None, YES)["act"])     # no Jev, no guess


class StretchTest(unittest.TestCase):
    def test_the_count_resets_when_the_session_turns_busy_or_works_but_not_for_its_own_probe_turn(self):
        stretches = Stretches()
        stretches.sent(row(), NOW)
        self.assertEqual(1, stretches.probes("ios"))
        stretches.observe(row(state="busy", last_turn_at=NOW - 60), NOW + 20)           # busy with the probe's own turn
        stretches.observe(row(last_turn_at=NOW + 15), NOW + 40)                        # the probe's reply ended
        self.assertEqual(1, stretches.probes("ios"))
        stretches.sent(row(), NOW + 3300)
        self.assertEqual(2, stretches.probes("ios"))
        stretches.observe(row(state="busy"), NOW + 3300 + 600)                         # busy on its own
        self.assertEqual(0, stretches.probes("ios"))
        stretches.sent(row(), NOW)
        stretches.observe(row(last_turn_at=NOW + 900), NOW + 1000)                     # a turn of its own ended
        self.assertEqual(0, stretches.probes("ios"))


class AutopilotProbeTest(unittest.TestCase):
    def test_a_due_probe_is_typed_logged_and_not_sent_twice_before_its_proof(self):
        autopilot, panes, wake, log = pilot({"ios": {"within_hour": .9, "never": .1}})
        self.assertEqual(1, autopilot.step([row()]))
        self.assertEqual([("w1:p2", PROBE_TEXT)], panes.typed)
        sent = [r for r in log.records if r.get("kind") == "probe" and r.get("event") == "sent"]
        self.assertEqual(KEEP_WARM, sent[0]["reason"].split(":")[0])
        self.assertEqual([1], [r["n"] for r in log.records if r.get("event") == "probe_sent"])
        autopilot.step([row()])
        self.assertEqual(1, len(panes.typed))  # its proof is still pending

    def test_nothing_is_typed_without_a_forecast_when_off_or_at_the_cap(self):
        autopilot, panes, _, _ = pilot({})
        autopilot.step([row()])
        self.assertEqual([], panes.typed)
        autopilot, panes, _, _ = pilot({"ios": {"within_hour": .9, "never": .1}}, keep_warm_probe_on=False)
        autopilot.step([row()])
        self.assertEqual([], panes.typed)
        autopilot, panes, wake, _ = pilot({"ios": {"within_hour": .9, "never": .1}})
        autopilot.stretches.sent(row(), NOW - 3400)
        autopilot.stretches.sent(row(), NOW - 3400)
        autopilot.stretches.sent(row(), NOW - 3400)
        autopilot.step([row()])
        self.assertEqual(([], []), (panes.typed, wake.asked))  # capped: Jev is not even asked

    def test_a_session_jev_expects_never_to_wake_gets_neither_a_probe_nor_the_spot_compaction(self):
        over = dict(over=True, context=300_000, spot=280_000, last_turn_at=NOW - 56 * 60)
        autopilot, panes, _, _ = pilot({"ios": {"within_hour": .1, "never": .9}})
        autopilot.step([row(**over)])
        self.assertEqual([], panes.typed)
        autopilot, panes, _, _ = pilot({"ios": {"within_hour": .1, "never": .1}})  # hours later, over its spot: compacted while warm
        autopilot.step([row(**over)])
        self.assertEqual([("w1:p2", "/compact")], panes.typed)

    def test_the_stretch_survives_a_restart_and_a_refused_pane_is_held(self):
        autopilot, panes, _, log = pilot({"ios": {"within_hour": .9, "never": .1}})
        autopilot.step([row()])
        again = Autopilot(autopilot.controls, autopilot.thresholds, log, FixedClock(NOW), lambda line: None)
        self.assertEqual(1, again.stretches.probes("ios"))
        refusing = pilot({"ios": {"within_hour": .9, "never": .1}})[0]
        refusing.controls.panes = FakePanes(fails=True)
        refusing.step([row()])
        self.assertEqual(0, refusing.stretches.probes("ios"))  # nothing was sent, so nothing counts
        self.assertIn("ios", refusing.unreachable)


class WakeAdapterTest(unittest.TestCase):
    def test_jev_is_asked_the_two_wake_questions_and_its_answers_become_the_forecast(self):
        classifier = FakeClassifier({"wake ios": {"wakes_within_hour": 0.8, "never_wakes": 0.05}})
        forecast = JevWakeForecast(classifier).forecast(row(), NOW - 3400, NOW)
        self.assertEqual({"within_hour": 0.8, "never": 0.05}, forecast)
        self.assertEqual(["wake ios"], classifier.asked)
        self.assertEqual(57, classifier.states["wake ios"]["idle"]["minutes_since_its_last_real_turn"])

    def test_a_session_row_carries_the_break_even_cap_of_its_price_card(self):
        warm = built_row(150_000)["keep_warm"]
        self.assertTrue(warm["eligible"])
        self.assertGreater(warm["cap"], 10)  # a cold rewrite costs about 38 probes on the 5.5 cards
        self.assertFalse(built_row(600_000)["keep_warm"]["eligible"])  # over 1.75x its sweet spot


class ProbeProofTest(unittest.TestCase):
    def test_the_probe_is_proved_by_a_cache_read_and_refuted_by_a_rewrite(self):
        autopilot, panes, _, log = pilot({"ios": {"within_hour": .9, "never": .1}})
        autopilot.step([row()])
        action = autopilot.controls.actions[0]
        probe = COMMANDS["probe"]
        warm = replace(stats(150_000, last_turn=NOW + 30), last_read=149_000, last_write=500, last_context=150_000)
        cold = replace(warm, last_read=0, last_write=150_000)
        self.assertIn("read 149k of 150k from the cache", probe.proof(action, {}, warm))
        self.assertEqual("", probe.refutation(action, {}, warm))
        self.assertIn("already cold", probe.refutation(action, {}, cold))
        self.assertEqual("", probe.proof(action, {}, cold))
        partial = replace(warm, last_read=10_000, last_write=1_000)  # neither a warm read nor a rewrite: not proved, not refuted
        self.assertEqual(("", ""), (probe.proof(action, {}, partial), probe.refutation(action, {}, partial)))
        self.assertEqual("", probe.proof(action, {}, replace(warm, last_turn_at=NOW - 10)))  # a turn from before the probe

    def test_a_permission_dialog_has_no_input_box_so_nothing_is_typed_into_it(self):
        rule = "─" * 40
        dialog = "\n".join([rule, " Bash command", "   git push origin main", " Do you want to proceed?", " ❯ 1. Yes", "   2. No"])
        self.assertIsNone(input_text(dialog))


if __name__ == "__main__":
    unittest.main()

import unittest
from dataclasses import replace

from cockpit.compaction.inputs_from_stats import inputs_for
from cockpit.compaction.sweet_spot import compaction_cost, cycle_cost_per_turn, extra_per_turn, sweet_spot
from cockpit.compaction.sweet_spot_inputs import SweetSpotInputs
from cockpit.sessions.session_row import compaction_costs
from cockpit.transcripts.recovery_span import RecoverySpan
from cockpit.transcripts.session_stats import Compaction, SessionStats
from tests.builders import prices

# The verifier's worked example E1 (research/scripts/m.py, research/raw/compaction-model.json).
E1 = SweetSpotInputs("claude-opus-5-5", 3600, P=117_212, F_s=46_630, S=20_000, T_s=0, g=2_779, g_p90=2_779,
                     y=519, q=0, kind="measured", basis="E1")


def stats(compactions=(), model="claude-opus-5-5", effort="high"):
    return SessionStats(session_id="s", title="", model=model, effort=effort, ttl_seconds=3600, context_now=200_000,
                        floor=72_000, last_turn_at=1.0, tokens_24h=0, growth=[3_000] * 20, outputs=[500] * 20,
                        gaps=[10.0] * 20, compactions=list(compactions), haiku_over_step=0)


class SweetSpotTest(unittest.TestCase):
    def test_e1_matches_the_verifier(self):
        card = prices().card_for("claude-opus-5-5", 100_000)
        self.assertAlmostEqual(0.9880984, compaction_cost(E1, card), places=6)
        spot = sweet_spot(E1, card, None)
        self.assertAlmostEqual(282_920.34, spot.trigger, places=1)
        self.assertEqual(315_000, spot.window)  # trigger + 33k, on the 5k grid
        self.assertAlmostEqual(0.0894719, cycle_cost_per_turn(280_000, E1, card), places=6)

    def test_haiku_grid_matches_the_verifiers_best_window(self):
        haiku = SweetSpotInputs("claude-haiku-5-5", 3600, P=72_212 + 35_000, F_s=46_630, S=10_000, T_s=0,
                                g=2_779, g_p90=2_779, y=519, q=0, kind="measured", basis="E8")
        self.assertEqual(205_000, sweet_spot(haiku, prices().card_for("claude-haiku-5-5", 100_000), None).trigger)

    def test_a_haiku_window_rounds_down_so_it_compacts_under_the_price_step(self):
        haiku = SweetSpotInputs("claude-haiku-5-5", 3600, P=72_212, F_s=46_630, S=10_000, T_s=0,
                                g=2_779, g_p90=2_779, y=519, q=0, kind="measured", basis="cap")
        spot = sweet_spot(haiku, prices().card_for("claude-haiku-5-5", 100_000), 99_000)
        # Rounded up, a 100k trigger got a 135k window, which compacts at 102k: over the step.
        self.assertLessEqual(spot.window - 33_000, spot.trigger)

    def test_a_haiku_window_compacts_at_its_sweet_spot_and_5k_under_the_step(self):
        card = prices().card_for("claude-haiku-5-5", 100_000)
        coordinator = SweetSpotInputs("claude-haiku-5-5", 3600, P=73_745, F_s=26_280, S=0, T_s=585, g=895, g_p90=1_565,
                                      y=585, q=0, kind="measured", basis="the coordinator, 2026-11-05")
        spot = sweet_spot(coordinator, card, None)
        self.assertEqual((95_000, 128_000), (spot.trigger, spot.window))  # was 125k, which compacted at 92k
        at_the_step = sweet_spot(replace(coordinator, P=88_000), card, None)
        self.assertEqual((100_000, 128_000), (at_the_step.trigger, at_the_step.window))

    def test_a_recovery_is_charged_only_over_the_normal_turns_it_replaced(self):
        span = RecoverySpan(fresh=0, write=12_000, read=180_000, out=1_500, requests=3, ended_by="edit")
        cut = Compaction(at=0.0, trigger="manual", pre=200_000, post=60_000, first_context=60_000, first_cached=0, recovery=span)
        inputs = SweetSpotInputs("claude-opus-5-5", 3600, P=60_000, F_s=0, S=0, T_s=0, g=2_000, g_p90=2_000,
                                 y=300, q=0, kind="measured", basis="test")
        # spent 15k + 18k + 7.5k = 40.5k; three normal turns at 60k cost 3 x (6k + 2.5k + 1.5k) = 30k
        self.assertEqual(10_500, compaction_costs(stats([cut]), inputs)[0]["recovery"])

    def test_the_quality_cap_bounds_the_sweet_spot(self):
        self.assertEqual(200_000, sweet_spot(E1, prices().card_for("claude-opus-5-5", 100_000), 200_000).trigger)

    def test_extra_cost_per_turn_over_the_sweet_spot(self):
        card = prices().card_for("claude-opus-5-5", 100_000)
        spot = sweet_spot(E1, card, None)
        self.assertAlmostEqual(0.0, extra_per_turn(spot.trigger, spot, E1, card))
        # r*c + w*g + o*y at 400k over the same at 282.9k: 0.112612 / 0.089196 - 1
        self.assertAlmostEqual(0.2625, extra_per_turn(400_000, spot, E1, card), places=3)

    def test_the_ceiling_is_where_carrying_a_chat_costs_one_compaction_inside_its_bounds(self):
        from dataclasses import replace
        from cockpit.compaction.ceiling import ceiling
        card = prices().card_for("claude-opus-5-5", 100_000)
        spot = sweet_spot(E1, card, None)
        self.assertAlmostEqual(1.25 * spot.trigger, ceiling(E1, card, spot))  # q 0: chats never end, so the low bound
        some = replace(E1, q=0.1)
        expected = some.P + 0.1 * spot.compaction_cost / card.at(some.P).cache_read
        self.assertTrue(1.25 * spot.trigger < expected < 2.5 * spot.trigger)
        self.assertAlmostEqual(expected, ceiling(some, card, spot))
        self.assertAlmostEqual(2.5 * spot.trigger, ceiling(replace(E1, q=1), card, spot))

    def test_a_model_without_a_price_card_has_no_sweet_spot(self):
        self.assertIsNone(prices().card_for("claude-opus-4-8", 100_000))

    def test_fable_has_its_own_flat_card(self):
        card = prices().card_for("claude-fable-5-1", 100_000)
        self.assertEqual((0.25, 20.0, 50.0), tuple(round(v * 1e6, 2) for v in (card.at(500_000).cache_read, card.at(0).write_1h, card.at(0).output)))

    def test_sonnet_reads_its_cache_at_half_the_opus_price(self):
        # The pricing page's footnote 2: 0.05x input on both, so $0.10 on Sonnet 5.5; the claude-api skill's $0.20 is stale (panel 8d90c5).
        sonnet, opus = (prices().card_for(m, 100_000).at(0) for m in ("claude-sonnet-5-5", "claude-opus-5-5"))
        self.assertEqual((0.10, 0.20), (round(sonnet.cache_read * 1e6, 2), round(opus.cache_read * 1e6, 2)))
        self.assertEqual({1_000_000}, {prices().window_of(m) for m in prices().models})


class InputsTest(unittest.TestCase):
    def test_own_compactions_are_measured(self):
        measured = stats([Compaction(1.0, "auto", 300_000, 90_000, 110_000, 60_000)])
        inputs = inputs_for(measured, [], None)
        self.assertEqual(("measured", 110_000, 60_000, 30_000), (inputs.kind, inputs.P, inputs.F_s, inputs.S))

    def test_without_its_own_compaction_peers_on_the_same_model_and_effort_are_provisional(self):
        peer = stats([Compaction(1.0, "auto", 300_000, 90_000, 120_000, 60_000)])
        self.assertEqual(("provisional", 120_000), (inputs_for(stats(), [peer], None).kind, inputs_for(stats(), [peer], None).P))

    def test_with_no_compaction_anywhere_the_documented_example_is_a_heuristic(self):
        inputs = inputs_for(stats(), [stats(effort="medium")], None)
        self.assertEqual(("heuristic", 72_000 + 45_000), (inputs.kind, inputs.P))


if __name__ == "__main__":
    unittest.main()

import unittest

from cockpit.compaction.price_card import FlatCard, per_million
from cockpit.compaction.sweet_spot import SweetSpot
from cockpit.compaction.sweet_spot_inputs import SweetSpotInputs
from cockpit.idle_cost.idle_gap import IdleGap
from cockpit.idle_cost.idle_gaps import idle_gaps
from cockpit.idle_cost.idle_policies import BREAK_EVEN, CAP_ONE, COMPACT, TODAY, Rules, actual, price_gap, probes_needed

OPUS = FlatCard(per_million(4.0, 5.0, 8.0, 0.20, 20.0))  # input, 5m write, 1h write, cache read, output per million
RULES = Rules(probe_output_tokens=20, probe_max_spot_multiple=1.75, margin_s=300)
INPUTS = SweetSpotInputs(model="claude-opus-5-5", ttl_seconds=3600, P=40_000, F_s=30_000, S=10_000, T_s=500, g=2_000, g_p90=3_000,
                         y=500, q=0.0, kind="measured", basis="test")
COLD, PROBE = 0.78, 0.0204  # (8 - 0.2) per M * 100k tokens; 0.2 per M * 100k + 20 tokens * 20 per M
CHEAP_COMPACT = SweetSpot(trigger=100_000, window=0, compaction_cost=0.001, kind="measured")
DEAR_COMPACT = SweetSpot(trigger=100_000, window=0, compaction_cost=5.0, kind="measured")


def gap(seconds, context=100_000, compacted=False):
    return IdleGap(seconds, context, compacted)


def price(policy, g, spot=DEAR_COMPACT):
    return price_gap(policy, g, OPUS, 3600, INPUTS, spot, RULES)


class IdleCostTest(unittest.TestCase):
    def test_only_stretches_over_the_cache_life_are_gaps_and_a_compaction_inside_is_flagged(self):
        rows = [{"t_first": 0, "t_last": 10, "context": 90_000}, {"t_first": 100, "t_last": 110, "context": 91_000},
                {"t_first": 5_000, "t_last": 5_010, "context": 92_000}]
        found = idle_gaps(rows, [{"at": 3_000}], 3600, 0)
        self.assertEqual((IdleGap(4_890, 91_000, True),), found)

    def test_policies_price_a_gap_at_the_cards_rates(self):
        short = gap(4_000)  # one probe at minute 55 reaches 6900 s
        self.assertEqual(1, probes_needed(short, 3600, RULES))
        self.assertAlmostEqual(COLD, price(TODAY, short).usd, places=4)
        self.assertAlmostEqual(PROBE, price(CAP_ONE, short).usd, places=4)
        long = gap(20_000)  # 6 probes: cap 1 gives up after the first and pays the rewrite
        self.assertEqual(6, probes_needed(long, 3600, RULES))
        self.assertAlmostEqual(PROBE + COLD, price(CAP_ONE, long).usd, places=4)
        self.assertAlmostEqual(6 * PROBE, price(BREAK_EVEN, long).usd, places=4)  # break-even is 38 probes at this card
        self.assertEqual(6, price(BREAK_EVEN, long).probes)

    def test_break_even_is_weighed_against_the_cheaper_of_rewrite_and_compaction(self):
        week = gap(7 * 86_400)
        spent = price(BREAK_EVEN, week, CHEAP_COMPACT)  # compaction at ~$0.013 is worth less than one probe: it just compacts
        self.assertEqual((0, 1), (spent.probes, spent.compacts))

    def test_a_free_probe_does_not_divide_by_zero(self):
        free = FlatCard(per_million(4.0, 5.0, 8.0, 0.0, 0.0))
        spent = price_gap(BREAK_EVEN, gap(20_000), free, 3600, INPUTS, DEAR_COMPACT, RULES)
        self.assertEqual((6, 0), (spent.probes, spent.cold))

    def test_above_the_ceiling_nothing_is_probed_and_actual_prices_what_happened(self):
        over = gap(4_000, context=200_000)  # over 1.75 x 100k
        self.assertEqual(0, price(BREAK_EVEN, over).probes)
        self.assertAlmostEqual(price(TODAY, over).usd, price(CAP_ONE, over).usd)
        self.assertEqual(1, price(COMPACT, over).compacts)
        spent = actual([gap(4_000), gap(4_000, compacted=True)], OPUS, 3600, INPUTS, DEAR_COMPACT)
        self.assertEqual((1, 1), (spent.cold, spent.compacts))


if __name__ == "__main__":
    unittest.main()

from cockpit.compaction.price_card import PriceCard
from cockpit.compaction.sweet_spot import SweetSpot
from cockpit.compaction.sweet_spot_inputs import SweetSpotInputs

# Owner, grill 20261018-172831 q1 E: the ceiling learns inside 1.25x to 2.5x its spot; neither end is a start value.
LOWEST, HIGHEST = 1.25, 2.5


def ceiling(inputs: SweetSpotInputs, card: PriceCard, spot: SweetSpot) -> float:
    """The context above which carrying it for the rest of a typical chat costs more than one compaction (COMPACTION.md
    cost model). A chat lasts 1/q turns (q: share of turns after an idle gap longer than the cache), each re-reading
    what a compaction would drop, (C - P) at the cached read price: q * C' / r over P."""
    r = card.at(inputs.P).cache_read
    carried = inputs.P + inputs.q * spot.compaction_cost / r if r else spot.trigger * HIGHEST
    return min(max(carried, spot.trigger * LOWEST), spot.trigger * HIGHEST)

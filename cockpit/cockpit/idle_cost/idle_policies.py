import math
from dataclasses import dataclass
from typing import Iterable, List, Optional

from cockpit.compaction.price_card import PriceCard
from cockpit.compaction.sweet_spot import SweetSpot
from cockpit.compaction.sweet_spot_inputs import SweetSpotInputs
from cockpit.idle_cost.idle_gap import IdleGap

TODAY, CAP_ONE, BREAK_EVEN, COMPACT = "today", "cap 1", "break-even", "compact"
POLICIES = (TODAY, CAP_ONE, BREAK_EVEN, COMPACT)


@dataclass(frozen=True)
class Spend:
    usd: float = 0.0
    tokens: int = 0     # raw tokens the idle handling processed: written, read or output
    cold: int = 0       # cache rewrites
    probes: int = 0
    compacts: int = 0

    def __add__(self, other: "Spend") -> "Spend":
        return Spend(self.usd + other.usd, self.tokens + other.tokens, self.cold + other.cold,
                     self.probes + other.probes, self.compacts + other.compacts)


@dataclass(frozen=True)
class Rules:
    probe_output_tokens: int   # heuristic: a fixed short message answered in a few words
    probe_max_spot_multiple: float
    margin_s: float            # a probe goes out this long before the cache expires


def cold(gap: IdleGap, card: PriceCard, ttl: int) -> Spend:
    """The rewrite beyond the read the next turn would have paid anyway: (w - r) * context."""
    p = card.at(gap.context)
    return Spend((p.write(ttl) - p.cache_read) * gap.context, gap.context, cold=1)


def probe(gap: IdleGap, card: PriceCard, rules: Rules) -> Spend:
    p = card.at(gap.context)
    return Spend(p.cache_read * gap.context + p.output * rules.probe_output_tokens, gap.context + rules.probe_output_tokens, probes=1)


def probes_needed(gap: IdleGap, ttl: int, rules: Rules) -> int:
    """Probes spaced one cache life minus the margin apart, up to the gap's end."""
    spacing = ttl - min(rules.margin_s, ttl / 2)
    return max(0, math.ceil(gap.seconds / spacing) - 1)


def idle_compact(gap: IdleGap, card: PriceCard, inputs: SweetSpotInputs, spot: SweetSpot) -> Spend:
    """C' with the summary read at the context the session had, not at P. The cheaper turns after it are not credited."""
    p = card.at(gap.context)
    return Spend(spot.compaction_cost + p.cache_read * (gap.context - inputs.P),
                 round(gap.context + inputs.S + inputs.T_s + inputs.P - inputs.F_s), compacts=1)


def capped(gap: IdleGap, cap: int, fallback: Spend, card: PriceCard, ttl: int, rules: Rules) -> Spend:
    """Probe up to `cap` times; if the gap needs more, the fallback is paid after all and the probes were spent for nothing."""
    needed = probes_needed(gap, ttl, rules)
    spend = Spend()
    for _ in range(min(needed, cap)):
        spend = spend + probe(gap, card, rules)
    return spend + fallback if needed > cap else spend


def alternative(gap: IdleGap, card: PriceCard, ttl: int, inputs: SweetSpotInputs, spot: SweetSpot) -> Spend:
    """What a probe is weighed against: the cheaper of letting the cache go cold and compacting at the idle point
    (docs/DECISIONS.md 2026-10-22, da7c4a, and the owner's "si un compact es 20 probes")."""
    return min(cold(gap, card, ttl), idle_compact(gap, card, inputs, spot), key=lambda spend: spend.usd)


def eligible_for_probe(context: float, spot: SweetSpot, rules: Rules) -> bool:
    return context <= rules.probe_max_spot_multiple * spot.trigger


def break_even_cap(gap: IdleGap, card: PriceCard, ttl: int, inputs: SweetSpotInputs, spot: SweetSpot, rules: Rules) -> tuple:
    """(probes worth sending, what they are weighed against). A card that prices a probe at 0 makes every probe worth
    it; the cap is then the gap's own need."""
    other = alternative(gap, card, ttl, inputs, spot)
    each = probe(gap, card, rules).usd
    return (int(other.usd // each) if each > 0 else probes_needed(gap, ttl, rules)), other


def price_gap(policy: str, gap: IdleGap, card: PriceCard, ttl: int, inputs: SweetSpotInputs, spot: SweetSpot, rules: Rules) -> Spend:
    eligible = eligible_for_probe(gap.context, spot, rules)
    if policy == COMPACT:
        return idle_compact(gap, card, inputs, spot)
    if policy == CAP_ONE and eligible:
        return capped(gap, 1, cold(gap, card, ttl), card, ttl, rules)
    if policy == BREAK_EVEN and eligible:
        cap, other = break_even_cap(gap, card, ttl, inputs, spot, rules)
        return capped(gap, cap, other, card, ttl, rules)
    return cold(gap, card, ttl)


def price_gaps(gaps: Iterable[IdleGap], card: PriceCard, ttl: int, inputs: SweetSpotInputs, spot: SweetSpot, rules: Rules) -> dict:
    """{policy: Spend} summed over the gaps."""
    return {policy: sum((price_gap(policy, g, card, ttl, inputs, spot, rules) for g in gaps), Spend()) for policy in POLICIES}


def actual(gaps: List[IdleGap], card: PriceCard, ttl: int, inputs: SweetSpotInputs, spot: SweetSpot) -> Spend:
    """What the idle gaps cost as they happened: a rewrite where nothing compacted, an idle compaction where one fell."""
    spend = Spend()
    for gap in gaps:
        spend = spend + (idle_compact(gap, card, inputs, spot) if gap.compacted else cold(gap, card, ttl))
    return spend

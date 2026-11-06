import math
from dataclasses import dataclass
from typing import Optional

from cockpit.compaction.price_card import PriceCard
from cockpit.compaction.sweet_spot_inputs import SweetSpotInputs

# Claude Code 2.1.301 compacts at W - min(maxOutputTokens, 20000) - 13000 (read from the binary; 1M - 33k = 967k).
TRIGGER_OFFSET = 33_000
GRID_STEP = 5_000
WINDOW_STEP = 1_000
# A compaction lands up to a turn past Claude Code's trigger (the coordinator's came up to 3.6k past it, 2026-11-05),
# so under a price step the trigger stays this far below the step.
STEP_MARGIN = 5_000
MAX_WINDOW = 1_000_000


@dataclass(frozen=True)
class SweetSpot:
    trigger: float      # context at which compacting costs least per turn
    window: int         # the --autocompact value that makes Claude Code compact there
    compaction_cost: float
    kind: str


def compaction_cost(inputs: SweetSpotInputs, card: PriceCard) -> float:
    """C' = r*P + o*(S + T_s) + w*(P - F_s) + R  (COMPACTION.md)."""
    p = card.at(inputs.P)
    r, w, o = p.cache_read, p.write(inputs.ttl_seconds), p.output
    return r * inputs.P + o * (inputs.S + inputs.T_s) + w * (inputs.P - inputs.F_s) + recovery_cost(inputs, card)


def recovery_cost(inputs: SweetSpotInputs, card: PriceCard) -> float:
    """R: the measured recovery mix at this session's prices, minus the normal turn it would have made anyway."""
    mix = inputs.recovery
    if mix is None:
        return 0.0
    p = card.at(inputs.P)
    spent = p.input * mix.fresh + p.write(inputs.ttl_seconds) * mix.write + p.cache_read * mix.read + p.output * mix.out
    return max(0.0, spent - turn_cost(inputs.P, inputs, card))


def recovery_tokens(inputs: SweetSpotInputs) -> float:
    mix = inputs.recovery
    return 0.0 if mix is None else max(0.0, mix.tokens - (inputs.P + inputs.g + inputs.y))


def turn_cost(context: float, inputs: SweetSpotInputs, card: PriceCard) -> float:
    p = card.at(context)
    return p.cache_read * context + p.write(inputs.ttl_seconds) * inputs.g + p.output * inputs.y


def cycle_cost_per_turn(trigger: float, inputs: SweetSpotInputs, card: PriceCard) -> Optional[float]:
    """Exact cost of one compaction cycle per turn with per-request prices (for the stepped Haiku card)."""
    if inputs.g <= 0 or trigger <= inputs.P + inputs.g:
        return None
    total, context, turns = 0.0, inputs.P, 0
    while context < trigger:
        p = card.at(context + inputs.g)
        total += p.cache_read * context + p.write(inputs.ttl_seconds) * inputs.g + p.output * inputs.y
        context, turns = context + inputs.g, turns + 1
    p = card.at(trigger)
    total += p.cache_read * trigger + p.output * (inputs.S + inputs.T_s)
    p = card.at(inputs.P)
    total += p.write(inputs.ttl_seconds) * (inputs.P - inputs.F_s) + recovery_cost(inputs, card)
    return total / turns


def sweet_spot(inputs: SweetSpotInputs, card: PriceCard, cap: Optional[float]) -> Optional[SweetSpot]:
    if inputs.g <= 0:
        return None
    cost = compaction_cost(inputs, card)
    if card.is_flat:
        p = card.at(inputs.P)
        r, w = p.cache_read, p.write(inputs.ttl_seconds)
        trigger = inputs.P + math.sqrt(2 * inputs.g * cost / (r + inputs.q * (w - r)))
    else:
        start = int(inputs.P + 2 * inputs.g_p90) // GRID_STEP * GRID_STEP + GRID_STEP
        costs = {t: cycle_cost_per_turn(t, inputs, card) for t in range(start, MAX_WINDOW - TRIGGER_OFFSET, GRID_STEP)}
        costs = {t: c for t, c in costs.items() if c is not None}
        if not costs:
            return None
        trigger = min(costs, key=costs.get)
    # Claude Code stops auto-compacting after 3 refills in a row, so leave room for two turns past P.
    trigger = max(trigger, inputs.P + 2 * inputs.g_p90)
    if cap:
        trigger = min(trigger, cap)
    # The window puts Claude Code's trigger on the sweet spot itself: rounded down to 5k it lost 3k on every grid trigger,
    # so the coordinator's 95k spot got a 125k window and compacted at 92k. Under a step it stays STEP_MARGIN below it.
    compacts_at = trigger if card.is_flat or trigger > card.step_tokens else min(trigger, card.step_tokens - STEP_MARGIN)
    window = int((compacts_at + TRIGGER_OFFSET) // WINDOW_STEP * WINDOW_STEP)
    return SweetSpot(trigger=trigger, window=min(window, MAX_WINDOW), compaction_cost=cost, kind=inputs.kind)


def extra_per_turn(context: float, spot: SweetSpot, inputs: SweetSpotInputs, card: PriceCard) -> float:
    """How much more a turn costs at this context than at the sweet spot, as a share."""
    at_spot = turn_cost(spot.trigger, inputs, card)
    return turn_cost(context, inputs, card) / at_spot - 1 if at_spot else 0.0

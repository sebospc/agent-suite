from typing import List, Optional

from cockpit.compaction.recovery_mix import RecoveryMix
from cockpit.compaction.stats_math import median, percentile, trimmed_mean
from cockpit.compaction.sweet_spot_inputs import SweetSpotInputs
from cockpit.transcripts.session_stats import SessionStats

LAST_CYCLES = 3
# Used only when no session of this model and effort has compacted yet (COMPACTION.md worked example E1).
EXAMPLE_SUMMARY = 20_000
EXAMPLE_REWORK = 25_000


def cycle_inputs(stats: SessionStats) -> Optional[dict]:
    measured = [c for c in stats.compactions if c.first_context][-LAST_CYCLES:]
    if not measured or stats.floor is None:
        return None
    return {
        "P": median([c.first_context for c in measured]),
        "F_s": median([c.first_cached for c in measured if c.first_cached is not None]) or stats.floor,
        # The summary is what a compaction leaves above the prefix that survives it. Not post minus the first
        # request: a transcript that starts with a resume begins far above the floor (phase 0 printed S < 0).
        "S": median([max(0, (c.post or c.first_context) - (c.first_cached or 0)) for c in measured]),
        "cycles": len(measured),
    }


def inputs_for(stats: SessionStats, fleet: List[SessionStats], recovery: Optional[RecoveryMix]) -> Optional[SweetSpotInputs]:
    g, y = trimmed_mean(stats.growth), trimmed_mean(stats.outputs)
    if not g or y is None or stats.floor is None:
        return None
    own = cycle_inputs(stats)
    if own:
        kind, basis, cycle = "measured", f"its last {own['cycles']} compaction{'s' if own['cycles'] > 1 else ''}", own
    else:
        peers = [c for c in (cycle_inputs(s) for s in fleet if s.model == stats.model and s.effort == stats.effort) if c]
        if peers:
            cycle = {key: median([p[key] for p in peers]) for key in ("P", "F_s", "S")}
            kind, basis = "provisional", f"no compaction yet; median of {len(peers)} {stats.model} {stats.effort} sessions"
        else:
            cycle = {"P": stats.floor + EXAMPLE_SUMMARY + EXAMPLE_REWORK, "F_s": stats.floor, "S": EXAMPLE_SUMMARY}
            kind, basis = "heuristic", "no compaction measured on this model yet; summary 20k and rework 25k from COMPACTION.md example E1"
    gaps = stats.gaps
    # The q term applies only where idle compaction cannot fire; it is on for the 1h cache of main threads.
    q = 0.0 if stats.ttl_seconds >= 3600 or not gaps else sum(1 for gap in gaps if gap > stats.ttl_seconds) / len(gaps)
    if kind == "measured" and recovery is not None and recovery.provisional:
        kind = "provisional"  # its own cycles, but the recovery cost is the fleet's until its kind has enough
    return SweetSpotInputs(model=stats.model, ttl_seconds=stats.ttl_seconds, P=cycle["P"], F_s=cycle["F_s"],
                           S=cycle["S"], T_s=y, g=g, g_p90=percentile(stats.growth, 90) or g,
                           y=y, q=q, kind=kind, basis=basis, recovery=recovery)

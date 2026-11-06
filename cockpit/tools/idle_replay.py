"""Idle-gap replay (bead mb-s347.1, step 1): prices every gap over the cache life of the real main-thread transcripts
under four policies, at each session's own price card. Pure arithmetic over files, no model call, nothing written.

    python3 tools/idle_replay.py [--days 7]
"""
import argparse
import glob
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from cockpit.compaction.inputs_from_stats import inputs_for
from cockpit.compaction.recovery_book import recovery_by_kind, recovery_for
from cockpit.compaction.sweet_spot import sweet_spot
from cockpit.composition import price_table, project_config, team_and_thresholds
from cockpit.idle_cost.idle_gaps import idle_gaps
from cockpit.idle_cost.idle_policies import POLICIES, Spend, TODAY, price_gaps, probes_needed
from cockpit.idle_cost.rules_from import rules_from
from cockpit.transcripts.transcript_file import TranscriptFile
from cockpit.transcripts.transcript_stats import session_stats

ROOT = os.path.expanduser("~/.claude/projects")
DAY = 86400


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    days = parser.parse_args().days
    now = time.time()
    since = now - days * DAY
    _, thresholds = team_and_thresholds(project_config())
    prices, rules = price_table(), rules_from(thresholds)
    step, idle_gap_s = thresholds.value("haiku_step_tokens"), thresholds.value("recovery_idle_gap_minutes") * 60
    quality_cap = thresholds.value("quality_cap_tokens")

    loaded = []
    for path in glob.glob(os.path.join(glob.escape(ROOT), "*", "*.jsonl")):
        if os.path.getmtime(path) < since:
            continue
        main_file = TranscriptFile(path)
        main_file.update()
        session_id = os.path.basename(path)[:-len(".jsonl")]
        loaded.append((session_id, main_file, session_stats(main_file, [], session_id, now, step, idle_gap_s)))
    fleet = [stats for _, _, stats in loaded]
    spans = [(c.at, None, c.recovery) for stats in fleet for c in stats.compactions if c.recovery]
    recovery = recovery_for(None, *recovery_by_kind(spans), thresholds.value("recovery_min_compactions"))

    results, skipped = {}, []
    needed = {1: 0, 2: 0, 3: 0}
    for session_id, file, stats in loaded:
        rows = [r for r in file.requests() if not r["sidechain"]]
        gaps = idle_gaps(rows, file.boundaries, stats.ttl_seconds, since)
        if not gaps:
            continue
        card = prices.card_for(stats.model, step)
        inputs = inputs_for(stats, fleet, recovery) if card else None
        spot = sweet_spot(inputs, card, quality_cap) if inputs else None
        if spot is None:
            skipped.append((session_id[:8], stats.model or "?", len(gaps), "no price card" if not card else "no sweet spot yet"))
            continue
        results[session_id[:8]] = (stats.model, stats.ttl_seconds, spot.trigger, len(gaps), price_gaps(gaps, card, stats.ttl_seconds, inputs, spot, rules))
        for gap in gaps:
            needed[min(3, max(1, probes_needed(gap, stats.ttl_seconds, rules)))] += 1

    fleet_total = {policy: Spend() for policy in POLICIES}
    print(f"Idle-gap replay, last {days} days, {len(results)} sessions priced, {len(skipped)} skipped. Per day, at list price from config/prices.json.\n")
    print("| session | model | TTL | spot | gaps | " + " | ".join(f"{p} $/d | {p} Mtok/d" for p in POLICIES) + " |")
    print("|---|---|---|---|---|" + "---|---|" * len(POLICIES))
    for name, (model, ttl, spot, count, spends) in sorted(results.items(), key=lambda kv: -kv[1][4][TODAY].usd):
        for policy in POLICIES:
            fleet_total[policy] = fleet_total[policy] + spends[policy]
        cells = " | ".join(f"{spends[p].usd / days:.2f} | {spends[p].tokens / days / 1e6:.2f}" for p in POLICIES)
        print(f"| {name} | {model.replace('claude-', '')} | {ttl // 60}m | {spot / 1000:.0f}k | {count} | {cells} |")
    cells = " | ".join(f"{fleet_total[p].usd / days:.2f} | {fleet_total[p].tokens / days / 1e6:.2f}" for p in POLICIES)
    print(f"| **fleet** | | | | {sum(r[3] for r in results.values())} | {cells} |\n")
    for policy in POLICIES:
        total = fleet_total[policy]
        print(f"{policy}: ${total.usd / days:.2f}/day, {total.tokens / days / 1e6:.2f} Mtok/day; {total.cold} rewrites, {total.probes} probes, {total.compacts} compactions in {days} days")
    print(f"\nGaps by probes needed to bridge them (1 / 2 / 3+): {needed[1]} / {needed[2]} / {needed[3]}")
    for row in skipped:
        print(f"skipped {row[0]} {row[1]}: {row[2]} gaps, {row[3]}")


if __name__ == "__main__":
    main()

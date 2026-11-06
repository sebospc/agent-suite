"""Measure context size, cache mix and relative cost per request from Claude Code transcripts.

Run: python3 -I measure_context.py [ROOT ...]   (default ROOT: /root/.claude/projects)
Prints only usage numbers, never message content.

Prices are USD per million tokens, copied from platform.claude.com/docs/en/about-claude/pricing.md
(model table lines 21, 29, 34-35; long-context rule line 222-224). Haiku 5.5 switches tier on
prompt length (input + cache_creation + cache_read) > 100,000.
"""
import glob
import json
import os
import statistics
import sys
from datetime import datetime

PRICES = {
    # base_in, write_5m, write_1h, cache_read, output
    "claude-opus-5-5": (4.0, 5.0, 8.0, 0.20, 20.0),
    "claude-sonnet-5-5": (2.0, 2.5, 4.0, 0.10, 10.0),
    "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
    "claude-fable-5-1": (10.0, 12.50, 20.0, 0.25, 50.0),  # the price page, 2026-10-15
    "claude-haiku-5-5@>100k": (0.50, 0.625, 1.0, 0.05, 2.50),
}
BUCKETS = [0, 25_000, 50_000, 75_000, 100_000, 150_000, 200_000, 300_000, 500_000, 1_000_001]


def price_for(model, context):
    if model == "claude-haiku-5-5" and context > 100_000:
        return PRICES["claude-haiku-5-5@>100k"]
    return PRICES.get(model)


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() if text else None


def pct(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q / 100 * (len(ordered) - 1))))
    return ordered[index]


def read_thread(path):
    """One transcript file = one thread. Dedupes streamed assistant entries by message.id."""
    requests, compactions, cost_states = {}, [], []
    for line in open(path, encoding="utf-8"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "system" and (
            entry.get("subtype") == "compact_boundary" or "compactMetadata" in entry
        ):
            meta = entry.get("compactMetadata") or {}
            compactions.append({k: meta.get(k) for k in ("trigger", "preTokens", "postTokens")})
        if entry.get("type") == "cost-state":
            cost_states.append(entry.get("modelUsage") or {})
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message") or {}
        usage = message.get("usage") or {}
        if not usage or message.get("model") in (None, "<synthetic>"):
            continue
        key = message.get("id") or entry.get("requestId")
        ts = parse_ts(entry.get("timestamp"))
        split = usage.get("cache_creation") or {}
        record = requests.setdefault(key, {
            "model": message.get("model"), "sidechain": bool(entry.get("isSidechain")),
            "t_first": ts, "t_last": ts, "usage": usage, "split": split,
            "iterations": len(usage.get("iterations") or []),
            "stop_reason": message.get("stop_reason"),
        })
        record["t_first"] = min(record["t_first"], ts)
        record["t_last"] = max(record["t_last"], ts)
        # Streamed blocks repeat usage; the last block carries the final output count.
        if (usage.get("output_tokens") or 0) >= (record["usage"].get("output_tokens") or 0):
            record["usage"], record["split"] = usage, split
        record["stop_reason"] = record["stop_reason"] or message.get("stop_reason")
    rows = []
    for record in sorted(requests.values(), key=lambda r: r["t_first"]):
        u = record["usage"]
        fresh = u.get("input_tokens") or 0
        write = u.get("cache_creation_input_tokens") or 0
        read = u.get("cache_read_input_tokens") or 0
        out = u.get("output_tokens") or 0
        w1h = record["split"].get("ephemeral_1h_input_tokens") or 0
        w5m = record["split"].get("ephemeral_5m_input_tokens") or 0
        if w1h + w5m != write:  # older transcripts lack the split; treat as 5m
            w5m, w1h = write, 0
        rows.append(dict(record, fresh=fresh, write=write, read=read, out=out, w1h=w1h, w5m=w5m,
                         context=fresh + write + read, path=path))
    for previous, row in zip(rows, rows[1:]):
        row["gap_s"] = row["t_first"] - previous["t_last"]
        row["growth"] = row["context"] - previous["context"]
    return rows, compactions, cost_states


def cost(row):
    p = price_for(row["model"], row["context"])
    if p is None:
        return None
    parts = {
        "fresh": row["fresh"] * p[0], "write5m": row["w5m"] * p[1], "write1h": row["w1h"] * p[2],
        "read": row["read"] * p[3], "output": row["out"] * p[4],
    }
    return {k: v / 1e6 for k, v in parts.items()}


def describe(label, values):
    if not values:
        print(f"  {label}: n=0")
        return
    print(f"  {label}: n={len(values)} min={min(values)} p10={pct(values, 10)} median={pct(values, 50)} "
          f"mean={statistics.mean(values):.0f} p90={pct(values, 90)} max={max(values)}")


def report(rows, label):
    print(f"\n=== {label}: {len(rows)} requests ===")
    if not rows:
        return
    describe("context tokens", [r["context"] for r in rows])
    growth = [r["growth"] for r in rows if "growth" in r]
    describe("growth per request (consecutive, same thread)", growth)
    describe("growth, positive only", [g for g in growth if g > 0])
    print(f"  requests with negative growth (context shrank): {sum(1 for g in growth if g < 0)}")
    describe("output tokens", [r["out"] for r in rows])
    snapshot = sum(1 for r in rows if r["stop_reason"] is None)
    print(f"  requests whose recorded usage has stop_reason=None (streaming snapshot, output undercounted): {snapshot}")
    describe("cache_creation tokens", [r["write"] for r in rows])
    totals = {k: sum(r[k] for r in rows) for k in ("fresh", "write", "w1h", "w5m", "read", "out")}
    grand = totals["fresh"] + totals["write"] + totals["read"] + totals["out"]
    print("  token mix: " + ", ".join(
        f"{k}={totals[k]} ({100 * totals[k] / grand:.2f}%)" for k in ("read", "write", "fresh", "out")))
    print(f"  cache writes by TTL: 1h={totals['w1h']} 5m={totals['w5m']}")
    print(f"  cache hit ratio (read / all input) = {totals['read'] / max(1, grand - totals['out']):.4f}")
    costs = [(r, cost(r)) for r in rows]
    priced = [(r, c) for r, c in costs if c]
    if priced:
        parts = {k: sum(c[k] for _, c in priced) for k in priced[0][1]}
        total = sum(parts.values())
        print(f"  list-price cost of {len(priced)} priced requests: ${total:.4f}; share: " + ", ".join(
            f"{k}={100 * v / total:.1f}%" for k, v in parts.items()))
    gap_report(rows)
    bucket_report(priced)


def gap_report(rows):
    print("  cache_creation vs idle gap before the request (gap = this request start - previous response end):")
    bands = [(0, 300, "<5m"), (300, 3600, "5m-1h"), (3600, 10**9, ">1h")]
    for low, high, name in bands:
        sel = [r for r in rows if "gap_s" in r and low <= r["gap_s"] < high]
        if not sel:
            print(f"    {name}: n=0")
            continue
        miss = [r["write"] / r["context"] for r in sel if r["context"]]
        full = sum(1 for r in sel if r["context"] and r["read"] < 0.5 * r["context"])
        print(f"    {name}: n={len(sel)} median write/context={pct(miss, 50):.4f} p90={pct(miss, 90):.4f} "
              f"requests where read<50% of context={full} max gap={max(r['gap_s'] for r in sel):.0f}s")
    spikes = [r for r in rows if r["context"] and r["write"] > 0.5 * r["context"] and "gap_s" in r]
    for r in spikes:
        print(f"    spike: context={r['context']} write={r['write']} read={r['read']} (1h={r['w1h']} 5m={r['w5m']}) "
              f"gap={r['gap_s']:.0f}s sidechain={r['sidechain']}")


def bucket_report(priced):
    print("  per context bucket: n, median output, median write, mean $/request, $ per 1k context, read share of $")
    for low, high in zip(BUCKETS, BUCKETS[1:]):
        sel = [(r, c) for r, c in priced if low <= r["context"] < high]
        if not sel:
            continue
        dollars = [sum(c.values()) for _, c in sel]
        read_share = sum(c["read"] for _, c in sel) / sum(dollars)
        mean_ctx = statistics.mean(r["context"] for r, _ in sel)
        print(f"    [{low // 1000}k,{high // 1000}k): n={len(sel)} out={pct([r['out'] for r, _ in sel], 50)} "
              f"write={pct([r['write'] for r, _ in sel], 50)} mean=${statistics.mean(dollars):.5f} "
              f"per1k=${1000 * statistics.mean(dollars) / mean_ctx:.6f} read_share={100 * read_share:.1f}%")
    xs = [r["context"] for r, _ in priced]
    ys = [sum(c.values()) for _, c in priced]
    if len(set(xs)) > 1:
        mx, my = statistics.mean(xs), statistics.mean(ys)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        print(f"  OLS $/request = {my - slope * mx:.5f} + {slope * 1e6:.4f} * (context in Mtok)")


def main(roots):
    paths = sorted({p for root in roots for p in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)})
    everything, compactions, last_cost_state = [], [], None
    for path in paths:
        rows, comp, states = read_thread(path)
        everything += rows
        compactions += comp
        if states:
            last_cost_state = states[-1]
    print(f"files={len(paths)} threads_with_requests={len({r['path'] for r in everything})}")
    print(f"models: { {m: sum(1 for r in everything if r['model'] == m) for m in {r['model'] for r in everything}} }")
    print(f"requests with usage.iterations>1: {sum(1 for r in everything if r['iterations'] > 1)}")
    report(everything, "ALL")
    report([r for r in everything if not r["sidechain"]], "MAIN THREAD (isSidechain=false)")
    report([r for r in everything if r["sidechain"]], "SIDECHAIN / SUBAGENT")
    print(f"\ncompact_boundary records: {len(compactions)}")
    for c in compactions:
        print(f"  {c}")
    if last_cost_state:
        print("\ncost-state cross-check (Claude Code's own costUSD, cumulative for the main session):")
        for model, mu in last_cost_state.items():
            p = PRICES.get(model)
            if not p:
                continue
            writes = mu.get("cacheCreationInputTokens", 0)
            rest = (mu.get("inputTokens", 0) * p[0] + mu.get("cacheReadInputTokens", 0) * p[3]
                    + mu.get("outputTokens", 0) * p[4]) / 1e6 + mu.get("webSearchRequests", 0) * 0.01
            implied_1h = ((mu.get("costUSD") - rest) * 1e6 - writes * p[1]) / (p[2] - p[1]) if writes else 0
            print(f"  {model}: costUSD=${mu.get('costUSD'):.6f} tokens in={mu.get('inputTokens')} "
                  f"out={mu.get('outputTokens')} read={mu.get('cacheReadInputTokens')} write={writes} "
                  f"web_search={mu.get('webSearchRequests')} -> implied 1h-write tokens={implied_1h:.0f} "
                  f"(must lie in [0, {writes}] if the price table is right)")
    window_model(everything)


def cycle_cost_per_request(model, window, floor, prefix, g, out, summary, rediscovery):
    """Exact sum over one compaction cycle with per-request (tiered) prices; returns $/request."""
    post = floor + summary + rediscovery
    if window <= post + g:
        return None
    total, ctx, n = 0.0, post, 0
    while ctx < window:
        _, _, w, r, o = price_for(model, ctx + g)
        total += (r * ctx + w * g + o * out) / 1e6
        ctx, n = ctx + g, n + 1
    _, _, w, r, o = price_for(model, window)
    total += (r * window + o * summary) / 1e6  # the summarizer request reads the full window
    _, _, w, r, o = price_for(model, post)
    total += w * (post - prefix) / 1e6  # first request after compaction rewrites all but the stable prefix
    return total / n


def window_model(rows):
    """Cost per request over a compaction cycle as a function of the auto-compact window W.

    Inputs measured from the transcripts: g (median main-thread growth per request), out (median
    main-thread output per request), floor (smallest main-thread context = startup prefix), prefix
    (tokens still read from cache on the >1h-gap requests = cross-session stable prefix).
    Inputs NOT measured here (no compact_boundary in this data): S = summary tokens, D = tokens the
    model re-reads after compaction because the summary dropped them. They are swept, not asserted.
    Closed form (flat prices): W* - P = sqrt(2 * g * (o*S + w*(P - prefix) + r*P) / r), P = floor + S + D.
    """
    main = [r for r in rows if not r["sidechain"] and r["model"] in PRICES]
    growth = [r["growth"] for r in main if "growth" in r]
    if not growth:
        return
    g, out = pct(growth, 50), pct([r["out"] for r in main], 50)
    floor = min(r["context"] for r in main)
    spikes = [r["read"] for r in main if r.get("gap_s", 0) > 3600]
    prefix = min(spikes) if spikes else 0
    windows = list(range(100_000, 1_000_001, 5_000)) + [95_000, 967_000]
    print(f"\nwindow model inputs: g={g} out={out} floor={floor} stable_prefix={prefix} (all measured, main thread)")
    for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        print(f"window model for {model} ($/request over a full cycle; S and D are swept inputs)")
        for summary in (10_000, 20_000):
            for rediscovery in (0, 25_000, 50_000):
                costs = {wdw: cycle_cost_per_request(model, wdw, floor, prefix, g, out, summary, rediscovery)
                         for wdw in sorted(set(windows))}
                costs = {k: v for k, v in costs.items() if v is not None}
                best = min(costs, key=costs.get)
                marks = " ".join(f"{k // 1000}k=${costs[k]:.5f}" for k in (95_000, 150_000, 200_000, 300_000, 500_000, 967_000) if k in costs)
                print(f"  S={summary} D={rediscovery}: best W={best} at ${costs[best]:.5f}/req | {marks}")

if __name__ == "__main__":
    main(sys.argv[1:] or ["/root/.claude/projects"])

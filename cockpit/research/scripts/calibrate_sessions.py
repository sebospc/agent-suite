"""Phase 0: the sweet-spot inputs of every session, from its main-thread transcript (COMPACTION.md).

Run: python3 calibrate_sessions.py [--days 14] [ROOT ...]   (default ROOT: ~/.claude/projects)
Prints numbers, model names and agent-<role> titles only; never message content or emails.
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
from transcript_requests import (EDIT_TOOLS, READ_TOOLS, is_subagent_file, most_common,  # noqa: E402
                                 percentile, read_transcript, transcript_paths, trimmed_mean)

RECENT_TURNS = 50
IDLE_FLOOR_S = 60  # shorter gaps are tool round trips inside one turn, not the owner or the team waiting
TTL_SECONDS = {"1h": 3600, "5m": 300}


def split_cycles(rows, boundaries):
    """Rows grouped by compaction cycle; cycle i>0 starts after boundary i-1."""
    cycles, times = [[]], sorted(b["t"] for b in boundaries if b["t"] is not None)
    edge = 0
    for row in rows:
        while edge < len(times) and (row["t_first"] or 0) > times[edge]:
            cycles.append([])
            edge += 1
        cycles[-1].append(row)
    return cycles


def rework(before, after):
    """Rows right after a boundary that only re-read targets read before it (heuristic, COMPACTION.md)."""
    seen = {target for row in before for tool, target in row["tools"] if tool in READ_TOOLS and target}
    rows = []
    for row in after:
        tools = row["tools"]
        if any(tool in EDIT_TOOLS for tool, _ in tools):
            break
        reads = [target for tool, target in tools if tool in READ_TOOLS]
        if not reads or any(target not in seen for target in reads):
            break
        rows.append(row)
    return rows


def session_numbers(path, data):
    rows = [r for r in data["requests"] if not r["sidechain"]]
    ttl = "1h" if sum(r["w1h"] for r in rows) > sum(r["w5m"] for r in rows) else "5m"
    ttl_s = TTL_SECONDS[ttl]
    gaps = []
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index else row
        row["growth"] = row["context"] - previous["context"]
        row["gap"] = (row["t_first"] or 0) - (previous["t_last"] or 0) if index else 0
        if index:
            gaps.append(row["gap"])
    cycles = split_cycles(rows, data["boundaries"])
    compactions, skipped = [], set()
    for index, boundary in enumerate(sorted(data["boundaries"], key=lambda b: b["t"] or 0)):
        before = [r for cycle in cycles[:index + 1] for r in cycle]
        after = cycles[index + 1] if index + 1 < len(cycles) else []
        first = after[0] if after else None
        redo = rework(before, after[1:]) if after else []
        skipped.update(id(r) for r in redo)
        if first:
            skipped.add(id(first))
        compactions.append(dict(boundary, P=first and first["context"], F_s=first and first["read"],
                                k_R=len(redo), D=sum(max(0, r["growth"]) for r in redo)))
    growth = []
    for row in rows[1:]:
        if id(row) not in skipped and row["gap"] <= ttl_s and row["growth"] >= 0:
            growth.append(row["growth"])
    recent_growth = growth[-RECENT_TURNS:]
    floor = rows[0]["context"] if rows else None
    for c in compactions:
        # Summary = what is left above the surviving prefix; post minus F goes negative when a transcript starts with a resume.
        c["S"] = (c.get("post") or c["P"]) - c["F_s"] if (c.get("post") or c["P"]) and c["F_s"] is not None else None
    idle = [g / 60 for g in gaps if g >= IDLE_FLOOR_S]
    last = data["boundaries"][-1] if data["boundaries"] else None
    now = rows[-1]["context"] if rows else None
    if last and rows and (last["t"] or 0) > (rows[-1]["t_first"] or 0):
        now = last.get("post") or now
    titles = [t for t in data["titles"] if t.startswith("agent-")]
    return {
        "id": os.path.splitext(os.path.basename(path))[0][:8], "name": titles[-1] if titles else "-",
        "model": most_common([r["model"] for r in rows]) or "-", "effort": most_common([r["effort"] for r in rows]) or "-",
        "ttl": ttl, "n": len(rows), "last": rows[-1]["t_last"] if rows else 0, "now": now, "F": floor,
        "g": trimmed_mean(recent_growth), "g90": percentile(recent_growth, 90),
        "y": trimmed_mean([r["out"] for r in rows[-RECENT_TURNS:]]),
        "q": sum(1 for g in gaps if g > ttl_s) / len(gaps) if gaps else None,
        "idle": idle, "haiku_over_100k": sum(1 for r in rows if "haiku" in (r["model"] or "") and r["context"] > 100_000),
        "compactions": compactions,
    }


def show(value, scale=1, digits=0):
    return "-" if value is None else f"{value / scale:.{digits}f}"


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=float, default=14)
    parser.add_argument("--summary", action="store_true", help="team sessions and medians only, short enough to paste")
    parser.add_argument("roots", nargs="*", default=["~/.claude/projects"])
    args = parser.parse_args(argv)
    paths = [p for p in transcript_paths(args.roots) if not is_subagent_file(p)]
    sessions = [session_numbers(p, read_transcript(p)) for p in paths]
    newest = max((s["last"] for s in sessions), default=0)
    sessions = [s for s in sessions if s["n"] and s["last"] >= newest - args.days * 86400]
    sessions.sort(key=lambda s: (s["name"], -s["n"]))
    print(f"main-thread transcripts: {len(paths)}; with requests in the last {args.days:g} days: {len(sessions)}")
    print("tokens in k; g, y = trimmed means of the last 50 turns; q = share of gaps over the TTL;"
          " idle = gaps of 1 min or more, in minutes")
    if args.summary:
        summary(sessions)
        return
    print("session  name                      model              effort  ttl  turns  ctx_now  F      g     g_p90  y     q     "
          "idle_n idle_p50 idle_p90 over_10m over_60m haiku>100k compactions")
    for s in sessions:
        idle = s["idle"]
        print(f"{s['id']} {s['name'][:25]:25} {s['model'][:18]:18} {s['effort'][:7]:7} {s['ttl']:4} {s['n']:6} "
              f"{show(s['now'], 1000):>7} {show(s['F'], 1000):>6} {show(s['g'], 1000, 1):>5} {show(s['g90'], 1000, 1):>6} "
              f"{show(s['y'], 1000, 2):>5} {show(s['q'], 0.01):>4}% {len(idle):6} {show(percentile(idle, 50), 1, 1):>8} "
              f"{show(percentile(idle, 90), 1, 1):>8} {sum(1 for m in idle if m > 10):8} {sum(1 for m in idle if m > 60):8} "
              f"{s['haiku_over_100k']:10} {len(s['compactions']):11}")
    print("\ncompactions: session name trigger pre_k post_k P_k F_s_k S_k k_R D_k")
    for s in sessions:
        for c in s["compactions"]:
            print(f"  {s['id']} {s['name'][:25]:25} {c.get('trigger') or '-':7} {show(c.get('pre'), 1000):>6} "
                  f"{show(c.get('post'), 1000):>6} {show(c['P'], 1000):>6} {show(c['F_s'], 1000):>6} "
                  f"{show(c['S'], 1000):>6} {c['k_R']:3} {show(c['D'], 1000):>6}")
    by_kind = defaultdict(list)
    for s in sessions:
        by_kind[(s["model"], s["effort"])].append(s)
    print("\nfleet medians by model and effort (seed for sessions with no compaction yet): sessions g_k y_k")
    for (model, effort), group in sorted(by_kind.items()):
        print(f"  {model[:18]:18} {effort[:7]:7} {len(group):3} {show(percentile([s['g'] for s in group if s['g'] is not None], 50), 1000, 1):>6} "
              f"{show(percentile([s['y'] for s in group if s['y'] is not None], 50), 1000, 2):>6}")


def compaction_medians(compactions):
    pick = lambda key: [c[key] for c in compactions if c.get(key) is not None]
    auto = sum(1 for c in compactions if c.get("trigger") == "auto")
    return (f"{len(compactions):3} ({auto} auto) pre={show(percentile(pick('pre'), 50), 1000):>5} P={show(percentile(pick('P'), 50), 1000):>5} "
            f"F_s={show(percentile(pick('F_s'), 50), 1000):>5} S={show(percentile(pick('S'), 50), 1000):>5} "
            f"k_R={show(percentile(pick('k_R'), 50)):>3} D={show(percentile(pick('D'), 50), 1000):>5}")


def summary(sessions):
    """Team sessions one line each, then fleet medians by model and effort including the compaction inputs."""
    team = [s for s in sessions if s["name"].startswith("agent-")]
    print(f"\nteam sessions (named agent-*): {len(team)}; tokens in k; compactions: count, then medians")
    for s in team:
        idle = s["idle"]
        print(f"  {s['id']} {s['name'][:24]:24} {s['model'][:17]:17} {s['effort'][:6]:6} ctx={show(s['now'], 1000):>5} "
              f"g={show(s['g'], 1000, 1):>4} y={show(s['y'], 1000, 2):>4} idle_p50={show(percentile(idle, 50), 1, 1)}m "
              f"haiku>100k={s['haiku_over_100k']} | {compaction_medians(s['compactions'])}")
    by_kind = defaultdict(list)
    for s in sessions:
        by_kind[(s["model"], s["effort"])].append(s)
    print("\nfleet by model and effort: sessions, g_k, y_k | compactions, then medians")
    for (model, effort), group in sorted(by_kind.items()):
        compactions = [c for s in group for c in s["compactions"]]
        print(f"  {model[:17]:17} {effort[:6]:6} {len(group):3} {show(percentile([s['g'] for s in group if s['g'] is not None], 50), 1000, 1):>5} "
              f"{show(percentile([s['y'] for s in group if s['y'] is not None], 50), 1000, 2):>5} | {compaction_medians(compactions)}")
    idle_all = [m for s in sessions for m in s["idle"]]
    print(f"\nidle gaps of 1 min or more, all sessions: n={len(idle_all)} p50={show(percentile(idle_all, 50), 1, 1)}m "
          f"p90={show(percentile(idle_all, 90), 1, 1)}m; over 10 m: {sum(1 for m in idle_all if m > 10)}, over 60 m: {sum(1 for m in idle_all if m > 60)}")


if __name__ == "__main__":
    main(sys.argv[1:])

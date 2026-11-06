"""Phase 0: the evidence behind the board thresholds (silent bead, blocker ask wait, one bead each).

Run: python3 measure_thresholds.py [--board ~/.agent-beads] [--beads FILE.jsonl]
Without --beads it runs `bd export --all` in the board folder. Prints ids, kinds and numbers only.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
from transcript_requests import parse_time, percentile  # noqa: E402

HOUR = 3600
SILENCE_MARKS_H = (2, 4, 6, 12, 24)
WAIT_MARKS_H = (0.25, 1, 4, 24)


def load_beads(board, path):
    if path:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    else:
        # bd waits on the board lock while a session writes; give it time, then fail loudly.
        text = subprocess.run(["bd", "export", "--all"], cwd=board, capture_output=True, text=True, timeout=60).stdout
    beads = []
    for line in text.splitlines():
        try:
            bead = json.loads(line)
        except ValueError:
            continue
        if isinstance(bead, dict) and bead.get("id", "").startswith("pg-"):
            beads.append(bead)
    return beads


def hours(seconds):
    return None if seconds is None else seconds / HOUR


def describe(label, values, marks):
    if not values:
        print(f"  {label}: n=0")
        return
    over = ", ".join(f">{m:g}h {100 * sum(1 for v in values if v > m) / len(values):.0f}%" for m in marks)
    print(f"  {label}: n={len(values)} p50={percentile(values, 50):.2f}h p90={percentile(values, 90):.2f}h "
          f"p95={percentile(values, 95):.2f}h max={max(values):.2f}h | {over}")


def ask_waits(panel):
    print("asks: time from asked to answered (panel.json answered[])")
    by_kind = defaultdict(list)
    for ask in panel.get("answered", []):
        asked, answered = parse_time(ask.get("asked")), parse_time(ask.get("answeredAt"))
        if asked and answered and answered >= asked:
            by_kind[ask.get("kind") or "none"].append(hours(answered - asked))
    for kind, waits in sorted(by_kind.items()):
        describe(kind, waits, WAIT_MARKS_H)
    now = datetime.now(timezone.utc).timestamp()
    open_ages = [(ask.get("kind"), hours(now - parse_time(ask.get("asked")))) for ask in panel.get("asks", []) if parse_time(ask.get("asked"))]
    print("  open now: " + (", ".join(f"{kind} {age:.1f}h" for kind, age in open_ages) or "none"))


def silences(beads, now):
    """Longest stretch without a visible update while in progress. Visible updates are started_at, each
    comment and closed_at; notes edits carry no time, so the gaps are an upper bound."""
    longest, durations = [], []
    for bead in beads:
        start = parse_time(bead.get("started_at"))
        if not start:
            continue
        end = parse_time(bead.get("closed_at")) or (now if bead.get("status") == "in_progress" else parse_time(bead.get("updated_at")))
        if not end or end < start:
            continue
        stamps = sorted([start, end] + [t for t in (parse_time(c.get("created_at")) for c in bead.get("comments") or []) if t and start < t < end])
        longest.append(hours(max(b - a for a, b in zip(stamps, stamps[1:])) if len(stamps) > 1 else 0))
        if bead.get("closed_at"):
            durations.append(hours(end - start))
    return longest, durations


def concurrency(beads, now):
    """Most beads one assignee held in progress at the same moment, from started_at to closed_at."""
    events = defaultdict(list)
    for bead in beads:
        start = parse_time(bead.get("started_at"))
        end = parse_time(bead.get("closed_at")) or (now if bead.get("status") == "in_progress" else None)
        if start and end and end > start:
            events[bead.get("assignee") or "none"] += [(start, 1), (end, -1)]
    result = {}
    for who, marks in events.items():
        held, peak, over_one, last = 0, 0, 0.0, None
        for stamp, step in sorted(marks):
            if last is not None and held > 1:
                over_one += stamp - last
            held, last = held + step, stamp
            peak = max(peak, held)
        result[who] = (peak, hours(over_one))
    return result


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", default="~/.agent-beads")
    parser.add_argument("--beads", help="a bd export --all JSONL file instead of running bd")
    args = parser.parse_args(argv)
    board = os.path.expanduser(args.board)
    now = datetime.now(timezone.utc).timestamp()
    print(f"read at {datetime.now().isoformat(timespec='seconds')}")
    with open(os.path.join(board, "panel.json"), encoding="utf-8") as handle:
        ask_waits(json.load(handle))
    beads = load_beads(board, args.beads)
    print(f"\nbeads: {len(beads)}; started at least once: {sum(1 for b in beads if b.get('started_at'))}")
    longest, durations = silences(beads, now)
    describe("longest silence while in progress (upper bound)", longest, SILENCE_MARKS_H)
    describe("claim to close", durations, (1, 6, 24, 72))
    if longest:
        print(f"  beads with any comment while in progress: {sum(1 for b in beads if b.get('started_at') and b.get('comments'))}"
              " (with few comments the silence is close to the claim-to-close time)")
    current = [b for b in beads if b.get("status") == "in_progress"]
    print("  in progress now, hours since last visible update: " + (", ".join(
        f"{b['id']} {hours(now - max([parse_time(b.get('started_at')) or 0] + [parse_time(c.get('created_at')) or 0 for c in b.get('comments') or []])):.1f}h"
        for b in current) or "none"))
    print("\nbeads held in progress at once, per assignee: peak, hours with more than one"
          " (upper bound: a bead set back to open keeps its started_at until it closes)")
    for who, (peak, over) in sorted(concurrency(beads, now).items(), key=lambda item: -item[1][0]):
        print(f"  {who[:24]:24} peak={peak} over_one={over:.1f}h")
    print("\nmessages per bead: not on the board; the cockpit counts them from transcripts once it keeps history")


if __name__ == "__main__":
    main(sys.argv[1:])

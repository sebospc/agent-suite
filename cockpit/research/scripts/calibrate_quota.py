"""Phase 0: how the plans' 5h and 7d limits weigh each kind of token (COMPACTION.md unknown 1).

Run:
  env -u CLAUDE_CONFIG_DIR cswap list --json > "$TMPDIR/cswap.json"
  python3 calibrate_quota.py --cswap "$TMPDIR/cswap.json" [--samples FILE] [--plan 2=max_20x] [ROOT ...]
Samples default to ~/.claude/handoff/state/usage-samples.jsonl (written by the balancer on every pick);
transcripts default to ~/.claude/projects. Prints account numbers and numbers only, never emails.
"""
import argparse
import bisect
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
from measure_context import price_for  # noqa: E402
from transcript_requests import email_at, parent_session_id, parse_time, read_transcript, transcript_paths  # noqa: E402
from least_squares import fit, nonnegative_fit, r_squared  # noqa: E402

# Same table as the balancer (pick_account.py PLAN_WEIGHTS): plan quota relative to Pro, (5h, 7d).
PLAN_WEIGHTS = {"pro": (1, 1), "max_5x": (5, 3.5), "max_20x": (20, 6)}
CATEGORIES = ("read", "w1h", "w5m", "fresh", "out")
MIN_SPAN_S = 1800
RESET_JITTER_S = 900
LIMIT_PCT = 99
MAX_UNATTRIBUTED = 0.10
CSWAP_CONFIGS = "~/.claude-swap-backup/configs"
# The owner, fc58d4 (2026-10-18): "acc 1 is max all the rest are pro". Used when cswap's config shows no tier.
OWNER_PLANS = {1: "max_5x"}
OWNER_PLANS_FROM = range(1, 22)  # the accounts with usage samples on 2026-10-18


def load_accounts(path, overrides):
    """number -> {email, plan}. Plan from the cswap config's oauthAccount tier, as the balancer reads it."""
    raw = []
    if path:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    listed = raw.get("accounts", raw) if isinstance(raw, dict) else raw
    accounts = {}
    for account in listed:
        number, email = account.get("number"), account.get("email")
        accounts[number] = {"email": normal(email), "plan": account.get("plan") or plan_from_config(number, email)}
    for number in OWNER_PLANS_FROM:
        accounts.setdefault(number, {"email": None})
    for number, account in accounts.items():
        if account.get("plan") not in PLAN_WEIGHTS:
            account["plan"] = OWNER_PLANS.get(number, "pro")
    for given in overrides:
        number, plan = given.split("=", 1)
        accounts.setdefault(int(number), {"email": None})["plan"] = plan
    return accounts


def normal(email):
    """Lower case, angle brackets and a display name dropped, and the local part without dots or a +tag, so
    "Name <a.b+2@gmail.com>" and "ab@gmail.com" compare equal (phase 0 run 2 matched 0 of 23 exactly)."""
    if not isinstance(email, str) or "@" not in email:
        return None
    address = email.strip().lower()
    if "<" in address and ">" in address:
        address = address[address.index("<") + 1:address.index(">")]
    local, _, domain = address.strip().rpartition("@")
    return local.split("+")[0].replace(".", "") + "@" + domain.strip()


def shape(email):
    """Letters as a, digits as 9: shows a format difference without showing the address."""
    return "".join("a" if c.isalpha() else "9" if c.isdigit() else c for c in email or "")


def plan_from_config(number, email):
    config = os.path.join(os.path.expanduser(CSWAP_CONFIGS), f".claude-config-{number}-{email}.json")
    try:
        with open(config, encoding="utf-8") as handle:
            oauth = json.load(handle).get("oauthAccount") or {}
    except (OSError, ValueError):
        return "unknown"
    tier = f"{oauth.get('organizationType')} {oauth.get('organizationRateLimitTier')}"
    if "max" not in tier:
        return "pro"
    return "max_20x" if "20x" in tier else "max_5x"


def load_samples(path):
    by_account = defaultdict(list)
    with open(os.path.expanduser(path), encoding="utf-8") as handle:
        lines = handle.readlines()
    for line in lines:
        try:
            sample = json.loads(line)
            usage = sample["usage"]
            by_account[sample["account"]].append((sample["t"], usage["fiveHour"], usage.get("sevenDay") or {}))
        except (ValueError, KeyError, TypeError):
            continue
    return {n: sorted(s, key=lambda x: x[0]) for n, s in by_account.items()}


def window_of(sample):
    """The 5h window's reset time. cswap reports it with jitter (run 3: 1,315 distinct values for one account in
    20 days), so two samples share a window when their resets are within RESET_JITTER_S."""
    text = sample[1].get("resetsAt")
    return parse_time(text) if parse_time(text) is not None else text


def same_window(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= RESET_JITTER_S
    return a == b


def intervals(samples):
    """One span per 5h window per account, from its first to its last sample. Short spans read 0: cswap's usage
    value lags (run 3: every 20-minute span showed no change), and the 5h % only moves in whole points."""
    spans, group = [], []
    for sample in samples:
        window = window_of(sample)
        if window is None:
            continue
        if group and not same_window(window_of(group[0]), window):
            spans.append((group[0], group[-1]))
            group = []
        group.append(sample)
    if group:
        spans.append((group[0], group[-1]))
    return [(a, b) for a, b in spans if b[0] - a[0] >= MIN_SPAN_S]


def requests_by_email(roots):
    emails_of = {}
    data_of = {}
    for path in transcript_paths(roots):
        data_of[path] = read_transcript(path)
        if data_of[path]["emails"]:
            emails_of.setdefault(parent_session_id(path), data_of[path]["emails"])
    rows = []
    for path, data in data_of.items():
        emails = emails_of.get(parent_session_id(path), [])
        for row in data["requests"]:
            rows.append(dict(row, email=normal(email_at(emails, row["t_first"]))))  # normal() also on cswap's side
    return sorted(rows, key=lambda r: r["t_first"] or 0)


def dollars(row):
    price = price_for(row["model"], row["context"])
    if price is None:
        return None
    return (row["fresh"] * price[0] + row["w5m"] * price[1] + row["w1h"] * price[2]
            + row["read"] * price[3] + row["out"] * price[4]) / 1e6


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cswap", help="saved output of: env -u CLAUDE_CONFIG_DIR cswap list --json")
    parser.add_argument("--samples", default="~/.claude/handoff/state/usage-samples.jsonl")
    parser.add_argument("--plan", action="append", default=[], help="N=pro|max_5x|max_20x, overrides the detected plan")
    parser.add_argument("roots", nargs="*", default=["~/.claude/projects"])
    args = parser.parse_args(argv)
    accounts = load_accounts(args.cswap, args.plan)
    number_of = {a["email"]: n for n, a in accounts.items() if a.get("email")}
    samples = load_samples(args.samples)
    rows = requests_by_email(args.roots)
    times = [r["t_first"] or 0 for r in rows]
    print(f"usage samples: {sum(len(s) for s in samples.values())} over accounts {sorted(samples)}")
    print("plans: " + ", ".join(f"{n}={accounts.get(n, {}).get('plan', 'unknown')}" for n in sorted(samples)))
    print(f"requests in transcripts: {len(rows)}; with an account email: {sum(1 for r in rows if r['email'])}")
    report_attribution(rows, number_of, samples)
    points, dropped = [], defaultdict(int)
    for number, account_samples in sorted(samples.items()):
        plan = accounts.get(number, {}).get("plan", "unknown")
        if plan not in PLAN_WEIGHTS:
            dropped["plan unknown (pass --plan)"] += len(intervals(account_samples))
            continue
        for start, end in intervals(account_samples):
            inside = rows[bisect.bisect_right(times, start[0]):bisect.bisect_right(times, end[0])]
            mine = [r for r in inside if number_of.get(r["email"]) == number]
            unknown = sum(r["context"] + r["out"] for r in inside if not r["email"])
            total = sum(r["context"] + r["out"] for r in inside if not r["email"] or number_of.get(r["email"]) == number)
            delta5 = float(end[1].get("pct") or 0) - float(start[1].get("pct") or 0)
            if delta5 < 0:
                dropped["5h % went down inside one window"] += 1
            elif float(end[1].get("pct") or 0) >= LIMIT_PCT:
                dropped["hit the 5h limit (use past it does not show)"] += 1
            elif total and unknown / total > MAX_UNATTRIBUTED:
                dropped["over 10% of tokens with no account email"] += 1
            elif not mine:
                dropped["no tokens on this account"] += 1
            else:
                weight5, weight7 = PLAN_WEIGHTS[plan]
                delta7 = float(end[2].get("pct") or 0) - float(start[2].get("pct") or 0)
                priced = [dollars(r) for r in mine]
                points.append({"plan": plan, "y": delta5 * weight5, "d5": delta5, "d7": delta7,
                               "x": [sum(r[c] for r in mine) / 1e3 for c in CATEGORIES],
                               "usd": sum(p for p in priced if p) if all(p is not None for p in priced) else None})
    print(f"windows used: {len(points)}; dropped: {dict(dropped) or 'none'}")
    moved = sorted(p["d5"] for p in points)
    if moved:
        print(f"  5h % change per used window: zero in {sum(1 for d in moved if d == 0)}, median {moved[len(moved) // 2]:g}, max {moved[-1]:g}")
    if len(points) < 6:
        print("too few intervals for a fit; run again after a few more days of samples")
        return
    report_fits(points)
    report_weekly(points)


def report_attribution(rows, number_of, samples):
    """Counts only (never an email): how many transcript emails match a listed account, and where tokens land."""
    emails = {r["email"] for r in rows if r["email"]}
    print(f"distinct account emails in transcripts: {len(emails)}; matching an account cswap lists: "
          f"{sum(1 for e in emails if e in number_of)}")
    print("  shapes, transcripts: " + ", ".join(sorted({shape(e) for e in emails})[:6]))
    print("  shapes, cswap:       " + ", ".join(sorted({shape(e) for e in number_of})[:6]))
    domains = {e.rpartition("@")[2] for e in number_of}
    print(f"  transcript emails whose domain cswap also uses: {sum(1 for e in emails if e.rpartition('@')[2] in domains)}")
    first = min((s[0][0] for s in samples.values() if s), default=0)
    last = max((s[-1][0] for s in samples.values() if s), default=0)
    in_range = [r for r in rows if first <= (r["t_first"] or 0) <= last]
    by_account = defaultdict(int)
    for row in in_range:
        by_account[number_of.get(row["email"], "not listed" if row["email"] else "no email")] += row["context"] + row["out"]
    span = (last - first) / 86400 if last > first else 0
    print(f"samples span {span:.1f} days; tokens in that span by account (M): "
          + ", ".join(f"{k}={v / 1e6:.1f}" for k, v in sorted(by_account.items(), key=lambda kv: str(kv[0]))))
    for number, account_samples in sorted(samples.items()):
        gaps = [b[0] - a[0] for a, b in zip(account_samples, account_samples[1:])]
        windows = len({s[1].get("resetsAt") for s in account_samples})
        print(f"  account {number}: {len(account_samples)} samples, median gap {sorted(gaps)[len(gaps) // 2] if gaps else 0:.0f} s, "
              f"{windows} distinct 5h resetsAt values, {len(intervals(account_samples))} windows of 30 min or more")


def report_fits(points):
    ys = [p["y"] for p in points]
    raw = [[sum(p["x"])] for p in points]
    k_raw = fit(raw, ys)
    print("\nwhat moves the 5h %, in Pro-plan % points (Max 5x and 20x scaled by 5 and 20):")
    print(f"  raw tokens:   {k_raw[0]:.5f} % per 1k tokens of any kind, R2={r_squared(raw, ys, k_raw):.3f}")
    usd = [p for p in points if p["usd"] is not None]
    if len(usd) >= 6:
        xs = [[p["usd"]] for p in usd]
        k_usd = fit(xs, [p["y"] for p in usd])
        print(f"  list dollars: {k_usd[0]:.3f} % per $ at list price, R2={r_squared(xs, [p['y'] for p in usd], k_usd):.3f}")
    xs = [p["x"] for p in points]
    coefficients = nonnegative_fit(xs, ys)
    print(f"  per category, none below 0: R2={r_squared(xs, ys, coefficients):.3f}; % per 1k tokens: "
          + ", ".join(f"{c}={k:.5f}" for c, k in zip(CATEGORIES, coefficients)))
    if len(usd) >= 6:
        opus = price_for("claude-opus-5-5", 0)
        print("  list dollars implies for Opus 5.5, % per 1k tokens: "
              + ", ".join(f"{c}={k_usd[0] * price * 1000 / 1e6:.5f}" for c, price in
                          zip(CATEGORIES, (opus[3], opus[2], opus[1], opus[0], opus[4]))))
    print(f"  balancer COLD_TURN_PRO_PCT_PER_1K_TOKENS (now 0.054): 1h write, per category {coefficients[1]:.4f}"
          + (f", from list dollars {k_usd[0] * price_for('claude-opus-5-5', 0)[2] * 1000 / 1e6:.4f}" if len(usd) >= 6 else ""))


def report_weekly(points):
    print("\nweekly vs 5h (balancer WEEKLY_PCT_IN_5H_PCT, now 6.5 for every plan): 5h points per weekly point")
    by_plan = defaultdict(list)
    for p in points:
        if p["d7"] > 0:
            by_plan[p["plan"]].append(p)
    for plan, group in sorted(by_plan.items()):
        print(f"  {plan}: {sum(p['d5'] for p in group) / sum(p['d7'] for p in group):.2f} over {len(group)} intervals")


if __name__ == "__main__":
    print(f"read at {datetime.now().isoformat(timespec='seconds')}")
    main(sys.argv[1:])

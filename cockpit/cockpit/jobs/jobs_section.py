from typing import Dict, List

from cockpit.controls.commands import kilo
from cockpit.display_time import clock_seconds, clock_time, when
from cockpit.prices.price_check import DAY, RETRY_S
from cockpit.transcripts.session_stats import SessionStats

# What runs by itself, one line each (the owner, 2026-10-16: "(the owner's words)"): no switches, a few words, when it last acted and what it did.


def job(id: str, name: str, what: str, last: str, did: str, level: str = "", detail: List[List[str]] = ()) -> dict:
    return {"id": id, "name": name, "what": what, "last": last, "did": did, "level": level, "detail": [list(p) for p in detail]}


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def self_compacted(stats_by_name: Dict[str, SessionStats], since: float) -> List[dict]:
    """Claude Code's own compactions today (trigger auto in the transcript): each one means the session reached its
    window before the sweet-spot rule compacted it (brain's pg-efsm: brain at 08:07, 267k to 22k, shown nowhere)."""
    return sorted(({"session": name, "at": c.at, "pre": c.pre, "post": c.post or c.first_context}
                   for name, stats in stats_by_name.items() for c in stats.compactions if c.trigger == "auto" and c.at >= since),
                  key=lambda c: -c["at"])


def by_itself(c: dict) -> str:
    return f"{c['session']} compacted by itself at {clock_time(c['at'])}, {kilo(c['pre'])} to {kilo(c['post'])}, before the sweet-spot rule did"


def autopilot_job(today: dict, skips: List[dict], now: float, itself: List[dict] = ()) -> dict:
    """The autopilot as one job like the others (the owner, 2026-10-16: "el autopilot es super importante ... deberia
    mostrarse claramente como un job como los demas"): every action today, not only its proved compactions."""
    rows = today["rows"]
    states = [r["state"] for r in rows]
    unproved = states.count("failed") + states.count("not_seen")
    waiting = states.count("waiting")
    detail = [["Switch", "on" if today["on"] else "off: autopilot_on is false in config/thresholds.json"],
              ["Today", ", ".join([plural(len(rows), "action"), f"{plural(today['done'], 'proved compaction')} cut {round(today['cut'] / 1000)}k",
                                   f"{waiting} waiting for its proof", f"{unproved} not proved"])]]
    detail += [["Left alone now", "; ".join(f"{s['session']}: {s['why']}" for s in skips)]] if skips else []
    detail += [["Compacted by itself", "; ".join(by_itself(c) for c in itself)]] if itself else []
    if not today["on"]:
        return job("autopilot", "Autopilot", "Compacts, clears and sets model and effort on idle sessions by its rules",
                   when(rows[0]["at"], now) if rows else "", "stopped: autopilot_on is false in config/thresholds.json", "amber", detail)
    did = "; ".join(p for p in (f"{plural(today['done'], 'proved compaction')} cut {round(today['cut'] / 1000)}k of context" if today["done"] else "",
                                f"{waiting} waiting for its proof" if waiting else "", f"{unproved} not proved" if unproved else "",
                                f"{plural(len(itself), 'session')} compacted by itself" if itself else "") if p)
    return job("autopilot", "Autopilot", "Compacts, clears and sets model and effort on idle sessions by its rules",
               when(rows[0]["at"], now) if rows else "", did or f"nothing to do today; {plural(len(skips), 'session')} left alone now",
               "amber" if unproved else "", detail)


def closed_when_off(rules: List[dict], rows: List[dict]) -> List[dict]:
    """A step still waiting for its proof stops waiting once its rule is turned off (pg-5xv8); a proof logged later wins."""
    off = {r["name"]: r["when"][len("Off: "):] for r in rules if r["when"].startswith("Off: ")}
    rule_of = lambda row: next((name for name in off if row["reason"].startswith(name)), None)
    return [{**row, "state": "stopped", "result": f"Closed without a proof: the rule is off ({off[rule_of(row)]})."}
            if row["state"] == "waiting" and rule_of(row) else row for row in rows]


def autopilot_jobs(rules: List[dict], today: dict, skips: List[dict], now: float, itself: List[dict] = ()) -> List[dict]:
    jobs = [autopilot_job(today, skips, now, itself)]
    for i, rule in enumerate(rules):
        mine = [r for r in today["rows"] if r["reason"].startswith(rule["name"])]
        latest = mine[0] if mine else None
        left = [s for s in skips if s["rule"] == rule["name"]]
        did = f"{latest['session']}: {latest['result']}" if latest else "nothing today"
        detail = [["Rule", rule["name"]], ["When", rule["when"]], ["Today", plural(len(mine), "action")]]
        detail += [["Left alone now", "; ".join(f"{s['session']}: {s['why']}" for s in left)]] if left else []
        if not today["on"]:
            jobs.append(job(f"rule-{i}", f"Autopilot: {rule.get('label', rule['name'])}", rule["short"], "", "stopped in config/thresholds.json", "amber", detail))
        elif rule["when"].startswith("Off: "):  # its own switch, set off on purpose (8b431d8), so not amber
            jobs.append(job(f"rule-{i}", f"Autopilot: {rule.get('label', rule['name'])}", rule["short"], when(latest["at"], now) if latest else "",
                            "stopped: " + rule["when"][len("Off: "):], "", detail))
        else:
            jobs.append(job(f"rule-{i}", f"Autopilot: {rule.get('label', rule['name'])}", rule["short"], when(latest["at"], now) if latest else "", did,
                            "amber" if latest and latest["state"] == "not_seen" else "", detail))
    return jobs


def next_runs(jobs: List[dict], read_at: float, refresh_s: float, prices: dict, paused: bool, now: float) -> None:
    """When each job runs next (the owner, 2026-10-16: "a cron column or something that explains when it is going to
    be executed")."""
    next_read = clock_seconds(read_at + refresh_s)
    for j in jobs:
        if j["id"].startswith("rule-") or j["id"] in ("autopilot", "jev"):
            j["next"] = "paused with the team" if paused else ("stopped" if j["did"].startswith("stopped") else
                                                              f"next read, {next_read}" + (", if a bead changed" if j["id"] == "jev" else ""))
        elif j["id"] == "read":
            j["next"] = next_read
        elif j["id"] == "prices":
            j["next"] = when(prices["tried_at"] + (RETRY_S if prices["error"] else DAY), now) if prices.get("tried_at") else "on the next read"
        elif j["id"] == "balancer":
            j["next"] = "when a session starts or moves (its hook)"


def jobs_section(rules: List[dict], today: dict, skips: List[dict], balancer: List[dict], balancer_error: str,
                 read_at: float, refresh_s: float, broken: int, prices: dict, jev: dict, now: float, paused: bool = False,
                 itself: List[dict] = ()) -> dict:
    today = {**today, "rows": closed_when_off(rules, today["rows"])}
    jobs = autopilot_jobs(rules, today, skips, now, itself)
    latest = balancer[0] if balancer else None
    jobs.append(job("balancer", "Balancer", "Puts each new or cold session on the account with most quota",
                    latest["t"] if latest else "",
                    latest["text"] if latest else (f"its log is not set up yet: {balancer_error}" if balancer_error else "no choice in 24 h"),
                    detail=[["Source", "the balancer's decision log (pg-81e3), last 24 h"]]))
    jobs.append(job("read", f"Read every {refresh_s:g} s", "Reads every source and rebuilds this page", when(read_at, now),
                    f"{broken} source{'' if broken == 1 else 's'} unavailable" if broken else "every source read",
                    "amber" if broken else ""))
    price_did = (prices["error"] and f"could not read the page: {prices['error']}") or \
                (f"{len(prices['differences'])} difference{'' if len(prices['differences']) == 1 else 's'} from config/prices.json"
                 if prices["differences"] else "config/prices.json matches the page")
    jobs.append(job("prices", "Price check, daily", "Compares config/prices.json with Anthropic's prices page",
                    when(prices.get("checked_at"), now), price_did if prices["tried_at"] else "not run yet",
                    "amber" if prices["differences"] or prices["error"] else "",
                    [["Page", prices["source"]], ["config/prices.json", f"as of {prices['as_of']}"]]
                    + [["Differs", d] for d in prices["differences"]]))
    jobs.append(job("jev", "Jev record", "Keeps Jev's suggestion beside what ran and how the bead ended",
                    "", f"{jev['beads']} beads, {jev['closed']} closed"
                    if jev["beads"] else ("nothing to record: Jev is not connected or no session holds a bead"),
                    "amber" if jev["error"] else "",
                    [["Classes", "; ".join(f"{c['name']}: {c['beads']} beads, {c['agreed']} as it ran, {c['closed']} closed"
                                           + (f", {round(c['per_bead'] / 1e6, 1)}M and {c['holds_per_bead']} HOLDs per bead" if c["per_bead"] else "")
                                           for c in jev["classes"])]] + ([["Error", jev["error"]]] if jev["error"] else [])))
    next_runs(jobs, read_at, refresh_s, prices, paused, now)
    log = sorted([{"at": r["at"], "t": when(r["at"], now), "state": r["state"], "id": r.get("id", ""), "wrong": r.get("wrong", ""),
                   "text": f"Autopilot: {r['session']}, {r['reason']}. {r['result']}"}
                  for r in today["rows"]]
                 + [{"at": c["at"], "t": when(c["at"], now), "state": "", "text": f"Claude Code: {by_itself(c)}."} for c in itself]
                 + [{"at": b["at"], "t": b["t"], "state": "", "text": f"Balancer: {b['text']}"} for b in balancer],
                 key=lambda r: -r["at"])
    return {"jobs": jobs, "log": log, "log_error": today.get("error", ""), "cut": today.get("cut", 0), "done": today.get("done", 0)}

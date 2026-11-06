import bisect
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from cockpit.team import role_of_name
from cockpit.milestone.tree import BeadTree
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.transcripts.history import History

WINDOW_S = 14 * 86400
SMALL = 5  # owner q6: a subgroup this small is reported, never used to pass or promote
DIMENSIONS = (("role", "Role"), ("type", "Bead type"), ("model", "Model"), ("effort", "Effort"))
RULE = "Shows; no level: a comparison is read against its sample sizes"
SOURCE = "the board (bd): each closed bead's session, start and close; transcripts: that session's requests in between (~)"


def finished_tasks(tree: Optional[BeadTree], history: Optional[History], now: float) -> List[dict]:
    """Each bead closed in 14 days with the tokens without cache its session spent on it: a request counts for the
    bead of that session that started last before it and was not closed yet (~: parallel beads share a session)."""
    if tree is None or history is None:
        return []
    beads = [b for b in tree.by_id.values() if b.status == "closed" and b.closed_at and b.closed_at >= now - WINDOW_S and b.assignee
             and (b.started_at or b.created_at)]
    by_session = defaultdict(list)
    for b in beads:
        by_session[b.assignee].append(b)
    requests = defaultdict(list)
    for r in history.requests:
        if r.session in by_session:
            requests[r.session].append(r)
    owner: Dict[int, str] = {}  # id of a request -> the bead it counts for
    for session, mine in by_session.items():
        listed = sorted(requests[session], key=lambda r: r.t)
        stamps = [r.t for r in listed]
        for b in sorted(mine, key=lambda b: b.started_at or b.created_at):  # a later start takes the overlap
            for r in listed[bisect.bisect_left(stamps, b.started_at or b.created_at):bisect.bisect_right(stamps, b.closed_at)]:
                owner[id(r)] = b.id
    spent = defaultdict(lambda: {"tokens": 0, "models": Counter(), "efforts": Counter()})
    for session in by_session:
        for r in requests[session]:
            if id(r) in owner:
                cell = spent[owner[id(r)]]
                cell["tokens"] += r.no_cache
                cell["models"][r.model] += 1
                cell["efforts"][r.effort] += 1
    return [{"bead": b.id, "role": role_of_name(b.assignee), "type": b.issue_type, "tokens": spent[b.id]["tokens"],
             "model": label(spent[b.id]["models"]), "effort": label(spent[b.id]["efforts"])} for b in beads if spent[b.id]["tokens"]]


def label(counts: Counter) -> str:
    value = counts.most_common(1)[0][0] if counts else ""
    return (value or "unknown").replace("claude-", "")


def comparison_rows(tasks: List[dict]) -> List[dict]:
    rows = []
    for key, name in DIMENSIONS:
        groups: Dict[str, List[int]] = defaultdict(list)
        for t in tasks:
            groups[t[key]].append(t["tokens"])
        for value, tokens in sorted(groups.items(), key=lambda g: -len(g[1])):
            rows.append({"id": f"{key}:{value}", "dimension": name, "value": value, "tasks": len(tokens),
                         "median": round(statistics.median(tokens)), "mean": round(statistics.mean(tokens)),
                         "sample": "small" if len(tokens) < SMALL else "ok"})
    return rows


def comparison_light(tasks: List[dict]) -> dict:
    rows = comparison_rows(tasks)
    columns = [("dimension", "By", "text"), ("value", "Group", "text"), ("tasks", "Tasks", "count"),
               ("median", "Median per task", "tokens"), ("mean", "Mean per task", "tokens"), ("sample", "Sample", "text")]
    small = sum(1 for r in rows if r["sample"] == "small")
    why = (f"{len(tasks)} beads closed in 14 days, tokens without cache per finished task by role, bead type, model and effort; "
           f"{small} of {len(rows)} groups have under {SMALL} tasks and decide nothing" if tasks else "No closed bead with its session's tokens in 14 days")
    return light("comparison", "Per task, compared", f"{len(tasks)} tasks", "ok" if tasks else "unknown", "", why + ".", RULE, SOURCE,
                 table("Tokens per finished task without cache, by group", columns, rows))

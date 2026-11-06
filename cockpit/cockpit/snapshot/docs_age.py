import re
from typing import Dict, List

from cockpit.display_time import day_time
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light

WINDOW_DAYS = 90  # git log reach; a doc not changed in it counts as changed when the window starts
PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)+\.\w+")
RULE = "WATCH when a doc names a file that changed more than doc_lag_days after the doc itself last did"
SOURCE = "git log --name-only of each team repo (90 d) and the tracked Markdown docs on disk"


def stale_docs(texts: Dict[str, Dict[str, str]], changes: Dict[str, Dict[str, float]], window_start: float, lag_s: float) -> List[dict]:
    """Design pg-o1sq Q13, team-wide: a doc whose named code moved on after it. Only paths that exist in the same
    repo's log count, so a path in prose that names nothing real is ignored; another doc is not code."""
    found = []
    for repo, docs in texts.items():
        changed = changes.get(repo, {})
        for doc, text in docs.items():
            doc_at = changed.get(doc, window_start)
            newer = sorted({(changed[p], p) for p in PATH.findall(text) if p in changed and not p.endswith(".md") and changed[p] > doc_at + lag_s},
                           reverse=True)
            if newer:
                found.append({"repo": repo, "doc": doc, "doc_at": doc_at, "newer": [(p, t) for t, p in newer]})
    return sorted(found, key=lambda d: -len(d["newer"]))


def docs_light(stale: List[dict], lag_days: float) -> dict:
    rows = [{"id": f"{d['repo']}:{d['doc']}", "doc": f"{d['repo']}/{d['doc']}", "doc_at": day_time(d["doc_at"]), "files": len(d["newer"]),
             "newest": f"{d['newer'][0][0]} ({day_time(d['newer'][0][1])})"} for d in stale]
    columns = [("doc", "Doc", "text"), ("doc_at", "Doc changed", "text"), ("files", "Named files changed after it", "count"),
               ("newest", "Newest", "text")]
    why = (f"{len(rows)} doc{'' if len(rows) == 1 else 's'} name files that changed more than {lag_days:g} days after the doc did; "
           "the doc may describe code that is gone" if rows else f"Every doc changed within {lag_days:g} days of the files it names")
    return light("docs_age", "Docs against code", f"{len(rows)} behind" if rows else "up to date", "watch" if rows else "ok", "", why + ".",
                 RULE, SOURCE, table("Docs older than the code they name", columns, rows))

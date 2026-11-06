from typing import Dict

from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.transcripts.cache_rewrites import CAUSES

RULE = "WATCH when a settings change or an unknown cause rewrote a cache in 24 h: those are the rewrites a rule could have avoided"
SOURCE = "transcripts: requests that wrote over half their context to the cache, by what came before them (~ heuristic)"


def rewrites_light(named: Dict[str, object]) -> dict:
    """Cache rewrites by cause (design pg-45v5): the biggest token cost, so every setting rule is judged against it."""
    rows = []
    for name, stats in sorted(named.items()):
        found = getattr(stats, "rewrites_24h", ())
        if not found:
            continue
        row = {"id": name, "session": name, "count": len(found)}
        row.update({cause: sum(tokens for c, tokens in found if c == cause) for cause in CAUSES})
        rows.append(row)
    totals = {cause: sum(r[cause] for r in rows) for cause in CAUSES}
    avoidable = totals["settings change"] + totals["unknown"]
    columns = [("session", "Session", "text"), ("count", "Rewrites", "count")] + [(c, c.capitalize(), "tokens") for c in CAUSES]
    why = (f"{sum(r['count'] for r in rows)} rewrites in 24 h wrote {sum(totals.values()):,} tokens; "
           f"{avoidable:,} of them after a settings change or for no known cause" if rows else "No cache rewrite in 24 h")
    return light("rewrites", "Cache rewrites", f"{sum(r['count'] for r in rows)} in 24 h", "watch" if avoidable else "ok", "", why + ".",
                 RULE, SOURCE, table("Cache rewrites of 24 h by cause, tokens written", columns, rows,
                                     [(c, c.capitalize(), "tokens", totals[c]) for c in CAUSES]))

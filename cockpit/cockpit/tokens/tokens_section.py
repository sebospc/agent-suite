from typing import List, Optional, Tuple

from cockpit.compaction.price_table import PriceTable
from cockpit.team import Team
from cockpit.thresholds import Thresholds
from cockpit.transcripts.history import History, Request

DAY, HOUR = 86400, 3600
ORIGINS = (("peer", "another session's message"), ("person", "you typing"), ("command", "a control"), ("own", "its own work"))


def pct(part: float, whole: float) -> Optional[int]:
    return round(part / whole * 100) if whole else None


def cache_hit(requests: List[Request]) -> Optional[float]:
    """Cache reads over every prompt token (fresh input, cache writes and reads), Gentle Shell's formula."""
    prompt = sum(r.tokens - r.out for r in requests)
    return round(100 * sum(r.read for r in requests) / prompt, 1) if prompt else None


def cost(requests: List[Request], prices: Optional[PriceTable], step_tokens: int, ttl_seconds: Optional[int]) -> Optional[float]:
    """USD at list price, each request on its own model's card; None when a model has no card, so no part is passed off
    as the whole. Cache writes are priced at the tier of the session's current TTL (heuristic: the tier is not logged)."""
    total = 0.0
    for r in requests:
        card = prices.card_for(r.model, step_tokens) if prices and r.model else None
        if card is None:
            return None
        p = card.at(r.context)
        total += (r.tokens - r.read - r.out - r.write) * p.input + r.write * p.write(ttl_seconds or 0) + r.read * p.cache_read + r.out * p.output
    return round(total, 2)


def tokens_section(rows: List[dict], history: Optional[History], days: List[dict], daily: Optional[Tuple[int, int, int]],
                   team: Team, thresholds: Thresholds, now: float, prices: Optional[PriceTable] = None) -> dict:
    """Where the tokens go (the owner, 2026-10-16: "una sección dedicada a tokens"): per day, per session over 24 h,
    above each session's sweet spot, and at a context where every turn is expensive. Every figure is without cache
    (fresh input and output, the owner 56fba6); with_cache, cache_read and cache_write are the detail."""
    day_ago = now - DAY
    recent = [r for r in (history.requests if history else []) if r.t >= day_ago]
    total = sum(r.no_cache for r in recent)
    high = thresholds.value("high_context_tokens")
    by_session = []
    for row in rows:
        mine = [r for r in recent if r.session == team.session_name(row["name"])]
        spent, with_cache = sum(r.no_cache for r in mine), sum(r.tokens for r in mine)
        if not with_cache:
            continue
        main = [r for r in mine if r.context]
        above = sum(r.no_cache for r in main if row["spot"] and r.context > row["spot"])
        # The start load is re-read by every turn, so its share of an average turn says how much of each turn is overhead.
        mean_context = sum(r.context for r in main) / len(main) if main else 0
        start = row.get("start_load")
        by_session.append({
            "start_load": start, "start_share": pct(start, mean_context) if start and mean_context else None,
            "name": row["name"], "account": row.get("account", ""), "model": row.get("model", ""), "context": row.get("context"),
            "input": spent - sum(r.out for r in mine), "output": sum(r.out for r in mine),
            "cache_read": sum(r.read for r in mine), "cache_write": sum(r.write for r in mine), "cache_hit": cache_hit(mine),
            "cost": cost(mine, prices, thresholds.value("haiku_step_tokens"), row.get("cache_ttl")),
            "idle_cost": (row.get("idle_cost") or {}).get("usd"),
            "tokens": spent, "with_cache": with_cache, "per_task": row.get("per_task"), "tasks": row.get("tasks_closed"), "share": pct(spent, total),
            "above_spot": pct(above, sum(r.no_cache for r in main)) if row["spot"] else None, "spot": row["spot"],
            "last_hour": sum(r.no_cache for r in mine if r.t >= now - HOUR),
            "origins": [{"who": label, "share": pct(sum(r.no_cache for r in mine if r.origin == key), spent)}
                        for key, label in ORIGINS if any(r.origin == key for r in mine)],
        })
    by_session.sort(key=lambda s: -s["tokens"])
    loads = sorted((r["start_load"], r["name"]) for r in rows if r.get("start_load"))
    finished = [d["no_cache"] for d in days[:-1] if d["no_cache"]]
    average = sum(finished) / len(finished) if finished else None
    today = daily[1] if daily else None
    over_pct = thresholds.value("tokens_day_over_avg_pct")
    return {
        "days": days, "today": today, "average": round(average) if average else None,
        # Today so far is compared with whole past days, so the mark can only come late, never falsely.
        "over_average": bool(today and average and today > average * (1 + over_pct / 100)), "over_pct": over_pct,
        "total_24h": total, "with_cache_24h": sum(r.tokens for r in recent), "cache_hit_24h": cache_hit(recent), "high": high,
        "high_share": pct(sum(r.no_cache for r in recent if r.context > high), total),
        "sessions": by_session, "top": by_session[0]["name"] if by_session else "",
        "start": {"median": loads[len(loads) // 2][0], "max": loads[-1][0], "max_session": loads[-1][1],
                  "watch_pct": thresholds.value("start_load_share_pct")} if loads else None,
    }

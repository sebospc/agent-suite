from dataclasses import dataclass
from typing import Dict, Optional

from cockpit.autopilot.rules import compaction_starts, idle_seconds
from cockpit.thresholds import Thresholds

# docs/REQUIREMENTS.md "Autopilot rules" 7; the first project's decision log, 2026-10-22 keep-warm rules.
KEEP_WARM = "Keep a cache warm with a probe"
PROBE_TEXT = "Keep-warm check from the cockpit. Reply with the single word ok and do nothing else."
PROBE_TURN_S = 300  # a one-word reply ends in seconds; one running past this counts as real work and resets the count, so it would probe more, not less


@dataclass
class Stretch:
    """One idle stretch: from the session's last real turn until it works again. Its probe count resets then."""
    idle_since: float   # the end of its last real turn
    probes: int
    last_probe_at: float


class Stretches:
    def __init__(self):
        self.by_session: Dict[str, Stretch] = {}

    def observe(self, row: dict, now: float) -> None:
        """Drops the stretch of a session that turned busy or took a turn of its own since its last probe."""
        found = self.by_session.get(row["name"])
        if found is None:
            return
        busy_on_its_own = row["state"] == "busy" and now - found.last_probe_at > PROBE_TURN_S
        worked = (row.get("last_turn_at") or 0) > found.last_probe_at + PROBE_TURN_S
        if row["state"] == "off" or busy_on_its_own or worked:
            del self.by_session[row["name"]]

    def probes(self, name: str) -> int:
        found = self.by_session.get(name)
        return found.probes if found else 0

    def idle_since(self, row: dict) -> float:
        found = self.by_session.get(row["name"])
        return found.idle_since if found else row["last_turn_at"]

    def sent(self, row: dict, now: float) -> Stretch:
        found = self.by_session.get(row["name"]) or Stretch(row["last_turn_at"], 0, now)
        found.probes, found.last_probe_at = found.probes + 1, now
        self.by_session[row["name"]] = found
        return found


def probe_state(row: dict, probes: int, thresholds: Thresholds, now: float, read_gap: float = 0) -> str:
    """no (the rule has nothing to say), wait (not yet due), capped (break-even count reached) or due."""
    warm, ttl = row.get("keep_warm"), row.get("cache_ttl")
    if not thresholds.value("keep_warm_probe_on") or not warm or not warm["eligible"] or not ttl:
        return "no"
    context = row["context"] or 0
    # The guard and the ceiling are compaction rules with their own reasons; a probe never competes with them.
    if row["state"] != "idle" or not row["pane"] or row["last_turn_at"] is None or row.get("haiku_guarded"):
        return "no"
    if row.get("ceiling") and context >= row["ceiling"]:
        return "no"
    # A compaction after its last request leaves nothing cached to keep warm: the summary was never sent, so a probe
    # writes the whole new context that its next turn writes anyway. 4 of the 6 cold probes of 10-21 and 10-22 came
    # minutes after one (two ceiling compactions, two of Claude Code's own while idle); none had outlived its cache.
    if (row.get("last_compaction_at") or 0) > row["last_turn_at"]:
        return "no"
    if not compaction_starts(ttl, thresholds, read_gap) <= idle_seconds(row, now) < ttl:
        return "wait"
    return "capped" if probes >= warm["cap"] else "due"


def verdict(row: dict, probes: int, forecast: Optional[dict], yes: float) -> dict:
    """The table of the first project's decision log, 2026-10-22: context band x expected wake. act: probe, hold (nothing at all, the cache
    goes cold) or leave (the other rules decide: over its spot that is the compaction while the cache is warm)."""
    cap = row["keep_warm"]["cap"]
    if forecast is None:
        return {"act": "leave", "why": "Jev gave no wake forecast, so nothing is probed on a guess"}
    if forecast["never"] >= yes:
        return {"act": "hold", "why": f"Jev expects no wake (never {forecast['never']:.2f}): it goes cold, nothing is spent"}
    if forecast["within_hour"] >= yes:
        return {"act": "probe", "why": f"Jev expects a wake within the hour ({forecast['within_hour']:.2f}); probe {probes + 1} of {cap}"}
    if not row["over"]:
        return {"act": "probe", "why": f"Jev expects a wake hours later and it is under its sweet spot; probe {probes + 1} of {cap}"}
    return {"act": "leave", "why": "Jev expects a wake hours later and it is over its sweet spot: compacted while the cache is warm"}


def probe_choice(row: dict, why: str) -> dict:
    return {"session": row["name"], "rule": KEEP_WARM, "kind": "probe", "text": PROBE_TEXT, "level": "",
            "reason": f"{round((row['context'] or 0) / 1000)}k context, idle; {why}"}

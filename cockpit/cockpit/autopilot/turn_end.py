from typing import Optional

from cockpit.thresholds import Thresholds

TURN_END = "Compact at a finished turn over its turn line"


def is_haiku(row: dict) -> bool:
    return "haiku" in (row.get("model_id") or row.get("model") or "").lower()


def turn_line(row: dict, thresholds: Thresholds) -> Optional[float]:
    """Its sweet spot, at most turn_end_max_tokens. The replay of 7 days of transcripts (2026-10-22) found the cost
    bottom flat from 150k to 200k and rising fast past 225k on every Opus and Sonnet session, while the ceilings cut them
    at 210k to 274k. Haiku has its own window just under the 100k price step, so it gets no turn line."""
    if not row.get("spot") or is_haiku(row):
        return None
    return min(row["spot"], thresholds.value("turn_end_max_tokens") * row.get("boost", 1))


def just_finished(idle: float, thresholds: Thresholds) -> bool:
    """A gap this long after a request ends the turn (the session is not between two tool calls). Past the window it was
    missed (a held read, a control still waiting), and the expiry rule decides instead, with what is known by then."""
    return thresholds.value("turn_end_gap_seconds") <= idle < thresholds.value("turn_end_window_minutes") * 60

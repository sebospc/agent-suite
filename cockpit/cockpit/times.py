from datetime import datetime
from typing import Optional


def parse_time(text) -> Optional[float]:
    """Epoch seconds from an ISO 8601 string as bd, panel.json and transcripts write it."""
    if not text or not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def hours_between(earlier: Optional[float], later: float) -> Optional[float]:
    return None if earlier is None else (later - earlier) / 3600

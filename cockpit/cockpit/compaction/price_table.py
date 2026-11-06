from datetime import date, datetime
from typing import Optional

from cockpit.compaction.price_card import FlatCard, PriceCard, SteppedCard, per_million

DAY = 86400


class PriceTable:
    """config/prices.json: list prices per model, the day they were read, and each model's own window."""

    def __init__(self, raw: dict):
        self.as_of = raw["as_of"]
        self.source = raw.get("source", "config/prices.json")
        self.models = raw["models"]

    def entry(self, model: str) -> Optional[dict]:
        # Transcripts carry dated ids (claude-opus-5-5-20261001), so a known id matches as a prefix.
        return next((v for k, v in self.models.items() if (model or "").startswith(k)), None)

    def card_for(self, model: str, haiku_step_tokens: int) -> Optional[PriceCard]:
        entry = self.entry(model)
        if entry is None:
            return None
        prices = per_million(entry["input"], entry["write_5m"], entry["write_1h"], entry["cache_read"], entry["output"])
        if entry.get("step_factor"):
            return SteppedCard(prices, haiku_step_tokens, entry["step_factor"])
        return FlatCard(prices)

    def window_of(self, model: str) -> Optional[int]:
        entry = self.entry(model)
        return entry.get("window") if entry else None

    def age_days(self, now: float) -> int:
        return (datetime.fromtimestamp(now).date() - date.fromisoformat(self.as_of)).days

    def stale_mark(self, now: float, max_days: int) -> str:
        """Mark B: prices change without notice, so an old card is named rather than trusted."""
        days = self.age_days(now)
        if days <= max_days:
            return ""
        return f"Prices in config/prices.json are from {self.as_of}, {days} days ago; check them against {self.source.split(',')[0]}."

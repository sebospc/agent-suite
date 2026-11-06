from abc import ABC, abstractmethod
from dataclasses import dataclass

MILLION = 1e6


@dataclass(frozen=True)
class Prices:
    """USD per token; the values and the day they were read are in config/prices.json."""
    input: float
    write_5m: float
    write_1h: float
    cache_read: float
    output: float

    def write(self, ttl_seconds: int) -> float:
        return self.write_1h if ttl_seconds >= 3600 else self.write_5m

    def scaled(self, factor: float) -> "Prices":
        return Prices(*(value * factor for value in (self.input, self.write_5m, self.write_1h, self.cache_read, self.output)))


class PriceCard(ABC):
    """Strategy: a flat card, or a stepped one whose whole request costs more above a prompt size."""

    @abstractmethod
    def at(self, prompt_tokens: float) -> Prices:
        pass

    @property
    @abstractmethod
    def is_flat(self) -> bool:
        pass


class FlatCard(PriceCard):
    def __init__(self, prices: Prices):
        self.prices = prices

    def at(self, prompt_tokens: float) -> Prices:
        return self.prices

    @property
    def is_flat(self) -> bool:
        return True


class SteppedCard(PriceCard):
    def __init__(self, below: Prices, step_tokens: int, factor: float):
        self.below = below
        self.above = below.scaled(factor)
        self.step_tokens = step_tokens

    def at(self, prompt_tokens: float) -> Prices:
        return self.above if prompt_tokens > self.step_tokens else self.below

    @property
    def is_flat(self) -> bool:
        return False


def per_million(*values: float) -> Prices:
    return Prices(*(v / MILLION for v in values))

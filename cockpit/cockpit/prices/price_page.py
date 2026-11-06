from abc import ABC, abstractmethod
from typing import Dict


class PricePage(ABC):
    """Anthropic's published list prices, read once a day to check config/prices.json."""

    @abstractmethod
    def read(self) -> Dict[str, dict]:
        """{model id prefix: {input, write_5m, write_1h, cache_read, output, step_factor?}} in USD per million tokens;
        raises SourceUnavailable when the page cannot be read or parsed."""

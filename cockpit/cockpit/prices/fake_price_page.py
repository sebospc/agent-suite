from typing import Dict, Optional

from cockpit.prices.price_page import PricePage
from cockpit.source_unavailable import SourceUnavailable


class FakePricePage(PricePage):
    def __init__(self, models: Optional[Dict[str, dict]], error: str = ""):
        self.models = models
        self.error = error
        self.reads = 0

    def read(self) -> Dict[str, dict]:
        self.reads += 1
        if self.models is None:
            raise SourceUnavailable(self.error or "page not reachable")
        return self.models

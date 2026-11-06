import re
import urllib.error
import urllib.request
from typing import Dict

from cockpit.prices.price_page import PricePage
from cockpit.source_unavailable import SourceUnavailable

COLUMNS = ("input", "write_5m", "write_1h", "cache_read", "output")
DOLLARS = re.compile(r"\$([0-9]+(?:\.[0-9]+)?)")
OVER = "for prompts over"


def model_id(cell: str) -> str:
    """'Claude Opus 5.5' -> 'claude-opus-5-5', the prefix config/prices.json keys on."""
    name = re.sub(r"\(.*?\)|\[.*?\]", "", cell).strip()
    return re.sub(r"[ .]+", "-", name.lower())


def parse_prices(markdown: str) -> Dict[str, dict]:
    """The first table of the pricing page: one row per model, five dollar columns. Haiku's row 'for prompts over'
    a size becomes its step factor."""
    found, over = {}, {}
    for line in markdown.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not cells[0].lower().startswith("claude"):
            continue
        values = [DOLLARS.search(c) for c in cells[1:]]
        if not all(values):
            continue
        prices = {k: float(v.group(1)) for k, v in zip(COLUMNS, values)}
        key = model_id(cells[0])
        target = over if OVER in cells[0].lower() else found
        target.setdefault(key, prices)  # the first table is the base price list; later tables repeat models
    for key, prices in over.items():
        if key in found and found[key]["input"]:
            found[key]["step_factor"] = round(prices["input"] / found[key]["input"], 4)
    if not found:
        raise SourceUnavailable("no price table found on the page; its layout may have changed")
    return found


class AnthropicPricePage(PricePage):
    def __init__(self, url: str, timeout_s: float):
        self.url = url
        self.timeout_s = timeout_s

    def read(self) -> Dict[str, dict]:
        try:
            # The page answers Python's default User-Agent with 403 (brain's report F5; Mozilla/5.0 gets 200).
            request = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0 (agent-suite cockpit price check)"})
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                text = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise SourceUnavailable(f"{self.url}: {error}")
        return parse_prices(text)

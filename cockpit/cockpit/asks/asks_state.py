from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AsksState:
    open: List[dict]
    answered: List[dict]
    read_at: float
    source: str

from typing import List, Optional


def trimmed_mean(values: List[float], share: float = 0.1) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    cut = int(len(ordered) * share)
    kept = ordered[cut:len(ordered) - cut] or ordered
    return sum(kept) / len(kept)


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q / 100 * (len(ordered) - 1))))]


def median(values: List[float]) -> Optional[float]:
    return percentile(values, 50)

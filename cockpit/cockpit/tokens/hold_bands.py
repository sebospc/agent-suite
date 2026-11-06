import bisect
from collections import defaultdict
from typing import Dict, List, Tuple

from cockpit.sessions.model_names import model_label
from cockpit.transcripts.history import History

# The owner's bands (decision 767efc): the sender's context when it sent the GO-REQ.
EDGES = (100_000, 200_000, 300_000)
LABELS = ("under 100k", "100-200k", "200-300k", "over 300k")


def hold_bands(history: History, min_reviews: int) -> dict:
    """HOLD rate per context band, per model (measured, decision 767efc: does quality drop as context grows). A review is a
    GO-REQ whose verdict is the first GO or HOLD naming the same bead and sha256 after it: HOLD if any HOLD, else GO. A patch
    sent twice counts once, at its first send; a GO-REQ with no verdict yet (or no sha256 to match) is left out and counted."""
    verdicts: Dict[Tuple[str, str], List] = defaultdict(list)
    for m in history.messages:
        if m.type in ("GO", "HOLD") and m.keys.get("sha256"):
            verdicts[(m.bead, m.keys["sha256"])].append(m)
    first: Dict[Tuple[str, str], object] = {}
    for request in sorted(history.review_requests, key=lambda r: r.t):
        first.setdefault((request.bead, request.sha256), request)
    counts: Dict[str, List[List[int]]] = defaultdict(lambda: [[0, 0] for _ in LABELS])  # model -> band -> [reviews, holds]
    waiting = 0
    for (bead, sha), request in first.items():
        after = [m for m in verdicts.get((bead, sha), []) if m.t >= request.t] if sha else []
        if not after:
            waiting += 1
            continue
        cell = counts[model_label(request.model)][bisect.bisect_right(EDGES, request.context)]
        cell[0] += 1
        cell[1] += any(m.type == "HOLD" for m in after)
    models = [{"model": model, "reviews": sum(n for n, _ in cells),
               "bands": [{"band": LABELS[i], "n": n, "holds": holds, "enough": n >= min_reviews,
                          "rate": round(holds / n * 100) if n >= min_reviews else None}
                         for i, (n, holds) in enumerate(cells)]}
              for model, cells in counts.items()]
    return {"models": sorted(models, key=lambda m: -m["reviews"]), "waiting": waiting, "min": min_reviews}

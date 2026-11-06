from collections import Counter
from typing import Dict, List, Optional

# Design chat N20: how far a thing can be trusted depends on where it lives.
TRUST = {"scratchpad": "not trusted", "agent memory": "that agent only, unreviewed", "a file": "trusted once committed"}


def said_vs_saved(answers: List[dict], decisions: Optional[str], beads_opened: List[dict], commits: Optional[List[dict]],
                  claims: Dict[str, dict], errors: Dict[str, str], blocks: Optional[List[dict]] = None) -> dict:
    """What was said today against what was saved where it lasts (design chat N18): the owner's answers and whether
    the decision log carries them, beads opened, commits landed, and replies that said saved without an id."""
    missing = [a for a in answers if decisions is not None and a["id"] not in decisions]
    without_id = {name: c["saved"] for name, c in claims.items() if c["saved"]}
    places = Counter(place for c in claims.values() for place in c["places"])
    return {
        "answers": len(answers), "not_in_decisions": [{"id": a["id"], "answer": a["answer"]} for a in missing],
        "decisions_error": errors.get("decisions", ""),
        "beads_opened": beads_opened, "commits": commits or [], "commits_error": errors.get("landed", ""),
        "without_id": without_id,
        "places": [{"place": p, "count": n, "trust": TRUST[p]} for p, n in places.most_common()],
        "guard": (f"{len(blocks)} repl{'y' if len(blocks) == 1 else 'ies'} stopped today: "
                  + "; ".join(f"{b.get('session', '?')}: {b.get('text', '')[:80]}" for b in blocks[-5:])) if blocks
                 else "no reply stopped today (nothing shows until brain's guard writes its log, TEAM_DEPENDENCIES 11)",
        "blocks": len(blocks or []),
    }

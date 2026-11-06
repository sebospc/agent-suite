from typing import List, Optional

from cockpit.board.bead import Bead

DEEP_LABELS = {"design", "architecture", "security"}
MECHANICAL_LABELS = {"mechanical", "chore"}


def from_fields(bead: Bead) -> Optional[dict]:
    """Structured fields first (design chat J1): what the bead's own type and labels already say. None when they
    decide nothing; {} when the bead is no task at all (a milestone or an epic), so Jev is not asked."""
    if bead.issue_type in ("milestone", "epic"):
        return {}
    if bead.issue_type == "chore" or MECHANICAL_LABELS & set(bead.labels):
        return {"mechanical": 1.0, "deep_reasoning": 0.0, "needs_history": 0.0, "wide_reading": 0.0}
    return None


def with_labels(beads: List[Bead], probabilities: dict) -> dict:
    """A design, architecture or security label on any of its open beads floors the session's deep reasoning."""
    if any(DEEP_LABELS & set(b.labels) for b in beads):
        return dict(probabilities, deep_reasoning=max(probabilities["deep_reasoning"], 0.9))
    return probabilities


def session_settings(p: dict, yes: float) -> dict:
    """The fixed table over the session verdict (design pg-o1sq Q12); its cut-offs are provisional and re-fitted
    from the Jev record within their ranges (Q14). A costly mistake never runs on Haiku."""
    deep, costly = p["deep_reasoning"] >= yes, p["mistake_costly"] >= yes
    if deep or costly:
        model, effort = "claude-opus-5-5", "xhigh" if p["deep_reasoning"] >= 0.85 else "high"
    elif p["mechanical"] >= yes:
        model, effort = "claude-haiku-5-5", "low"
    else:
        model, effort = "claude-sonnet-5-5", "medium"
    return {"model": model, "effort": effort, "window": "large" if p["wide_reading"] >= yes else "small", "why": why(p)}


def bead_start(p: dict, yes: float) -> dict:
    """The bead verdict: carry the context when the next bead needs what it worked out or is related to it."""
    carry = p["needs_history"] >= yes or p["related"] >= yes
    return {"needs_history": p["needs_history"] >= yes, "related": p["related"] >= yes, "long": p["long"] >= yes,
            "start": "carry its context" if carry else "fresh, after a clear", "bead_why": why(p)}


def why(p: dict) -> str:
    return ", ".join(f"{k.replace('_', ' ')} {v:.2f}" for k, v in p.items())

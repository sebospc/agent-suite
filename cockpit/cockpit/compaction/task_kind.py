from typing import Dict, List, Optional

from cockpit.board.bead import Bead

NO_BEAD = "no bead"
# Labels about the process, not the task: they would split one kind of work into many.
PROCESS_LABELS = {"dod", "nice"}


def kind_from_labels(bead: Bead) -> Optional[str]:
    labels = sorted(label for label in bead.labels if label not in PROCESS_LABELS and not label.startswith("from:"))
    return "+".join(labels) or None


def jev_category(probabilities: Dict[str, float], yes: float) -> str:
    """The judgment Jev is surest of, when it clears the yes cut-off; "plain" when none does."""
    best = max(probabilities, key=probabilities.get)
    return best.replace("_", " ") if probabilities[best] >= yes else "plain"


def bead_at(beads: List[Bead], assignee: str, at: float) -> Optional[Bead]:
    """The bead the session held at that moment: started before it and not closed yet; the latest started wins."""
    held = [b for b in beads if b.assignee == assignee and b.started_at and b.started_at <= at
            and (b.closed_at is None or at <= b.closed_at)]
    return max(held, key=lambda b: b.started_at) if held else None

from typing import Tuple

EFFORTS = ("low", "medium", "high", "xhigh")
KINDS = ("compact", "clear", "effort", "need")


def clear_permission(row: dict) -> Tuple[bool, str]:
    """Clear only at a task end: idle, holding no bead in progress, its notes saved, so nothing is lost."""
    if row["state"] != "idle":
        return False, "Busy. Clear it when its turn ends and its task is done."
    if row["holds"]:
        return False, "It still holds a bead in progress. Clear only at the end of a task."
    if row["notes_saved"] is False:
        return False, "Its notes were not saved after its last turn."
    return True, "Idle, no bead in progress: its next task starts from a small context."

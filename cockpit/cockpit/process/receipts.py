from typing import Dict, List

from cockpit.transcripts.history import PeerMessage

WEEK = 7 * 86400


def receipt_breaks(messages: List[PeerMessage], now: float) -> List[str]:
    """Each review names the patch it judged by its sha256 (the project's WORKFLOW "Messages"): a GO or HOLD must name a
    sha256 a GO-REQ sent for that bead, a LAND-READY one a GO approved, and LANDED needs a GO. Checked on this week's
    messages, against the 14 days read, so a chain that started earlier is not called broken."""
    sent: Dict[str, set] = {}
    approved: Dict[str, set] = {}
    breaks = []
    for m in sorted(messages, key=lambda m: m.t):
        if not m.bead or not m.type:
            continue
        sha = m.keys.get("sha256", "")
        recent = now - m.t <= WEEK
        if m.type in ("GO-REQ", "GO", "HOLD", "LAND-READY") and not sha:
            if recent:
                breaks.append(f"{m.type} on {m.bead} names no sha256")
            continue
        if m.type == "GO-REQ":
            sent.setdefault(m.bead, set()).add(sha)
        elif m.type in ("GO", "HOLD"):
            if sha not in sent.get(m.bead, set()) and recent:
                breaks.append(f"{m.type} on {m.bead} names sha256 {sha[:8]}, which no GO-REQ sent")
            if m.type == "GO":
                approved.setdefault(m.bead, set()).add(sha)
        elif m.type == "LAND-READY" and sha not in approved.get(m.bead, set()) and recent:
            breaks.append(f"LAND-READY on {m.bead} names sha256 {sha[:8]}, which no GO approved")
        elif m.type == "LANDED" and not approved.get(m.bead) and recent:
            breaks.append(f"LANDED on {m.bead} with no GO before it")
    return list(dict.fromkeys(breaks))

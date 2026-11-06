import os
import re
from typing import Dict, List, Optional

from cockpit.team import role_of_name
from cockpit.milestone.tree import BeadTree
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.transcripts.history import History

DAY = 86400
SETTLE_S = 7 * DAY   # owner, grill 20261018-172831 q6: a task is judged correct only after its 7-day window
WINDOW_S = 14 * DAY  # the history the snapshot reads
RULE = "WATCH when a reviewed bead closed in 14 days took a HOLD before its GO, was reopened or got a fix bead within 7 days"
SOURCE = "the board (bd), GO-REQ, HOLD and GO messages in transcripts (14 d), actions.jsonl bead_reopened"
PATCH_BEAD = re.compile(r"^((?:pg|mb)-[a-z0-9]{3,5}(?:\.\d+)*)(?:-[a-z0-9.-]+)?-v\d+\.patch$")  # pg-<bead>-vN.patch (brain's ruling, pg-45v5)


def rework_rows(tree: Optional[BeadTree], history: Optional[History], reopened: Dict[str, float], now: float) -> List[dict]:
    """Each bead closed in the last 14 days, with what it took after its first try (design pg-45v5 measure 3)."""
    if tree is None:
        return []
    messages = history.messages if history else []
    beads = list(tree.by_id.values())
    requested, reviews_by_bead = reviews_of(messages)
    requested |= {r.bead for r in history.review_requests} if history else set()  # the sender's copy, if the reviewer's is gone
    rows = []
    for bead in beads:
        if bead.status != "closed" or not bead.closed_at or bead.closed_at < now - WINDOW_S:
            continue
        reviews = sorted(reviews_by_bead.get(bead.id, []))
        first_go = next((t for t, kind in reviews if kind == "GO"), None)
        holds = sum(1 for t, kind in reviews if kind == "HOLD" and (first_go is None or t < first_go))
        fixes = sorted(b.id for b in beads if b.id != bead.id and b.created_at and bead.closed_at <= b.created_at <= bead.closed_at + SETTLE_S
                       and is_fix(b) and (bead.id in b.related or bead.id in (b.title or "") or bead.id in (b.description or "")))
        settled = now - bead.closed_at >= SETTLE_S
        reworked = bool(holds or bead.id in reopened or fixes)
        rows.append({"id": bead.id, "bead": bead.id, "type": bead.issue_type, "who": role_of_name(bead.assignee),
                     "holds": holds, "reviewed": first_go is not None, "reopened": bead.id in reopened, "fixes": ", ".join(fixes),
                     "verdict": ("not reviewed" if bead.id not in requested else "rework" if reworked
                                 else "not reviewed" if first_go is None else "correct" if settled else "pending")})
    return sorted(rows, key=lambda r: r["bead"])


def reviews_of(messages) -> tuple:
    """The beads a GO-REQ was sent for, and each bead's (time, GO or HOLD). Since 2026-10-14 a review's line 1 names its
    bead; before that only its sha256 does, matched to the GO-REQ that sent it, whose patch file names the bead."""
    requested, bead_of_sha = set(), {}
    for m in messages:
        if m.head == "GO-REQ":
            bead = m.bead or bead_of_patch(m.keys.get("patch", ""))
            if bead:
                requested.add(bead)
                if m.keys.get("sha256"):
                    bead_of_sha[m.keys["sha256"]] = bead
    reviews: Dict[str, list] = {}
    for m in messages:
        if m.head in ("GO", "HOLD"):
            bead = m.bead or same_patch(m.keys.get("sha256", ""), bead_of_sha)
            if bead:
                reviews.setdefault(bead, []).append((m.t, m.head))
    return requested, reviews


def bead_of_patch(patch: str) -> str:
    found = PATCH_BEAD.match(os.path.basename(patch))
    return found.group(1) if found else ""


def same_patch(sha: str, bead_of_sha: Dict[str, str]) -> str:
    """Messages give the sha256 at different lengths (8 hex or full), so one is a prefix of the other."""
    if len(sha) < 7:
        return ""
    return next((bead for sent, bead in bead_of_sha.items() if sent.startswith(sha) or sha.startswith(sent)), "")


def is_fix(bead) -> bool:
    """A follow-up that names a bead is a fix only when it is a bug or says so; a next step is not rework."""
    return bead.issue_type == "bug" or "fix" in (bead.title or "").lower()


def rework_light(rows: List[dict]) -> dict:
    settled = [r for r in rows if r["verdict"] in ("correct", "rework")]
    unreviewed = sum(1 for r in rows if r["verdict"] == "not reviewed")
    correct = sum(1 for r in settled if r["verdict"] == "correct")
    reworked = sum(1 for r in rows if r["verdict"] == "rework")
    columns = [("bead", "Bead", "text"), ("type", "Type", "text"), ("who", "Session", "text"), ("holds", "HOLDs before GO", "count"),
               ("reopened", "Reopened", "text"), ("fixes", "Fix beads, 7 d", "text"), ("verdict", "Verdict", "text")]
    shown = [dict(r, reopened="yes" if r["reopened"] else "no") for r in rows]
    why = (f"{len(rows)} beads closed in 14 days: {reworked} took rework, {correct} of {len(settled)} past their 7 days were correct "
           f"first time (GO without a HOLD before it, no reopen, no fix bead); {len(rows) - len(settled) - unreviewed} wait for their 7 days "
           f"and {unreviewed} had no GO-REQ or no GO, so they are not judged"
           if rows else "No bead closed in 14 days")
    return light("rework", "Rework", f"{reworked} of {len(rows)} reworked", "watch" if reworked else "ok", "", why + ".", RULE, SOURCE,
                 table("Beads closed in 14 days and what they took after the first try", columns, shown))

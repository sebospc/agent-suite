from typing import List, Optional

from cockpit.board.bead import OWNER, Bead
from cockpit.display_time import age, clock_time, day_time
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import BeadTree
from cockpit.times import parse_time


def owner_beads_without_ask(tree: BeadTree, criteria: Optional[Criteria], open_asks: List[dict]) -> List[Bead]:
    """Beads that wait on the owner with no ask: assigned to the owner, or an open done criterion the owner
    must approve, or a blocked done criterion (GRILL.md step 1)."""
    asked = {a.get("bead") for a in open_asks if a.get("bead")}
    waiting = [b for b in tree.by_id.values() if b.assignee == OWNER and b.status in ("in_progress", "blocked", "open")]
    if criteria:
        waiting += [b for b in criteria.open() if b.status == "blocked" or Criteria.waits_on_owner(b)]
    unique = {b.id: b for b in waiting if b.id not in asked}
    return sorted(unique.values(), key=lambda b: b.id)


def asks_view(open_asks: List[dict], waiting: List[Bead], now: float, source: str) -> dict:
    rows = []
    for ask in open_asks:
        asked = ask.get("asked")
        from_time = parse_age(asked, now)
        meta = f"{ask.get('kind', 'ask')} ask from {ask.get('by', 'unknown')}{', ' + from_time if from_time else ''}"
        if ask.get("bead"):
            meta += f" · bead {ask['bead']}"
        if not ask.get("rec"):
            meta += " · no recommendation given"
        rec = ask.get("rec") if isinstance(ask.get("rec"), dict) else {}
        rows.append({"id": ask.get("id", "?"), "text": ask.get("text", ""), "meta": meta, "is_ask": True,
                     "kind": ask.get("kind", ""), "options": list(ask.get("options") or []),
                     "rec": rec.get("option", ""), "why": rec.get("why", "")})
    for bead in waiting:
        why = "assigned to you" if bead.assignee == OWNER else ("a blocked done criterion" if bead.status == "blocked"
                                                                else "a done criterion that waits for your approval")
        rows.append({"id": bead.id, "text": bead.title, "is_ask": False, "kind": "parked" if bead.title.startswith("Parked") else "ticket",
                     "meta": f"{why} · {bead.status} since {day_time(bead.updated_at)} · not a question: brain writes one when it needs your answer"})
    asks_count, beads_count = len(open_asks), len(waiting)
    # The owner, 2026-10-16: "Your tasks", questions apart from tickets (16 rows read as 16 questions while 5 were).
    summary = (f"{asks_count} question{'' if asks_count == 1 else 's'}, "
               f"{beads_count} ticket{'' if beads_count == 1 else 's'}")
    return {"rows": rows, "summary": summary, "source": source, "askable": asks_count}


def answered_today(answered: List[dict], since: float) -> List[dict]:
    """Your asks' log: answers saved since local midnight, wherever the owner gave them, newest first."""
    stamped = [(parse_time(a.get("answeredAt")), a) for a in answered]
    today = sorted(((t, a) for t, a in stamped if t is not None and t >= since), key=lambda pair: -pair[0])
    return [{"id": a.get("id", "?"), "t": clock_time(t), "text": a.get("text", ""), "answer": a.get("answer", "")} for t, a in today]


def waiting_blockers(open_asks: List[dict], hours: float, now: float) -> List[dict]:
    """Blocker asks old enough to light the Asks light ACT: the session that asked waits for the answer and starts
    nothing else (owner, 2026-10-16, panel 4c9041)."""
    return [a for a in open_asks if a.get("kind") == "blocker" and parse_time(a.get("asked")) is not None
            and now - parse_time(a.get("asked")) >= hours * 3600]


def parse_age(stamp: Optional[str], now: float) -> str:
    asked = parse_time(stamp)
    return age(now - asked) if asked else ""

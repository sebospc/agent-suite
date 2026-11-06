from typing import Dict, List, Tuple

# Design pg-o1sq Q5: the owner's "wrong" click undoes a decision at the next idle moment when it can be undone, and
# always keeps it as a labelled example for Jev (Q4 G) and the re-fit (Q14).
LABELS_PER_SESSION = 5
KEEP_ID = "task:"
NO_UNDO = {
    "keep": "a keep typed nothing, so the click only stores the label",
    "compact": "its context is gone, so the click only stores the label (design Q5)",
    "clear": "its context is gone, so the click only stores the label (design Q5)",
    "model": "a typed /model is saved in ~/.claude/settings.json (brain's J5), so the click only stores the label",
    "effort": "a typed /effort is saved in ~/.claude/settings.json (brain's J5), so the click only stores the label",
    "relaunch": "it relaunched with team.json's own flags, which are the owner's choice; the click only stores the label",
}


def decisions(records: List[dict]) -> Dict[str, dict]:
    """id -> each decision the owner can mark wrong: every control the autopilot sent, and every TASK it kept."""
    found = {r["id"]: r for r in records if r.get("origin") == "autopilot" and r.get("event") == "sent"}
    found.update({KEEP_ID + r["task"]: dict(r, id=KEEP_ID + r["task"], kind="keep") for r in records
                  if r.get("event") == "task_start" and r.get("action") == "keep"})
    return found


def undo_of(decision: dict, records: List[dict]) -> Tuple[str, str]:
    """(the command that undoes it, or "" and why none): only a relaunch whose exit record kept an undo command has one,
    a resume of the same session id with team.json's own flags, so its conversation and files are kept."""
    kind = decision.get("kind", "")
    exit_record = next((r for r in records if r.get("event") == "relaunch_exit" and r.get("id") == decision["id"]), {})
    if kind == "relaunch" and exit_record.get("undo_command"):
        return exit_record["undo_command"], ""
    return "", NO_UNDO.get(kind, "the click only stores the label")


def wrong_record(decision: dict, undo: str, why: str, now: float) -> dict:
    return {"t": now, "event": "wrong", "origin": "owner", "of": decision["id"], "session": decision["session"],
            "kind": decision.get("kind", ""), "decision": decision.get("reason") or decision.get("why") or "", "undo": undo, "why": why}


def marked(records: List[dict]) -> Dict[str, dict]:
    return {r["of"]: r for r in records if r.get("event") == "wrong"}


def labels(records: List[dict]) -> Dict[str, List[dict]]:
    """Per session, its latest wrong clicks, as Jev sees them."""
    found: Dict[str, List[dict]] = {}
    for r in sorted((r for r in records if r.get("event") == "wrong"), key=lambda r: -r["t"]):
        mine = found.setdefault(r["session"], [])
        if len(mine) < LABELS_PER_SESSION:
            mine.append({"kind": r["kind"], "decision": r["decision"]})
    return found


def pending_undos(records: List[dict]) -> List[dict]:
    ended = {r.get("of") for r in records if r.get("event") in ("undo_sent", "undo_dropped")}
    return [r for r in records if r.get("event") == "wrong" and r.get("undo") and r["of"] not in ended]

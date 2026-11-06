import string
from typing import List, Optional

QUESTION_PREFIX = "ask-"

NO_REC = {"text": "No recommendation given",
          "why": "This ask was added before asks carried a recommendation (ask_owner.py, Oct 16), so none is shown."}


def letter(index: int) -> str:
    return string.ascii_uppercase[index]


def question_id(ask_id: str) -> str:
    """The question carries its ask id, so a round survives a cockpit restart without a side file."""
    return QUESTION_PREFIX + ask_id


def ask_id_of(question: str) -> Optional[str]:
    return question[len(QUESTION_PREFIX):] if question.startswith(QUESTION_PREFIX) else None


def question_for(ask: dict) -> dict:
    """One grill question per panel ask: its text, its context, its options lettered, its recommendation."""
    options = [{"k": letter(i), "text": text} for i, text in enumerate(ask.get("options") or [])]
    rec = ask.get("rec") if isinstance(ask.get("rec"), dict) and ask["rec"].get("option") else NO_REC
    return {"id": question_id(ask.get("id", "")), "round": 1, "title": ask.get("text", ""), "body": body_for(ask),
            "options": options, "rec": rec}


def body_for(ask: dict) -> str:
    lines = [f"Ask {ask.get('id')} from {ask.get('by', 'unknown')}" + (f", bead {ask['bead']}" if ask.get("bead") else "") + "."]
    if ask.get("reply"):
        lines.append(ask["reply"])
    coverage = ask.get("coverage") or {}
    for key, label in (("covered", "Covered"), ("fixed", "Fixed"), ("not_covered", "Not covered"), ("notCovered", "Not covered")):
        for item in coverage.get(key) or []:
            lines.append(f"{label}: {item}")
    return "\n\n".join(lines)


def build_round(open_asks: List[dict]) -> List[dict]:
    return [question_for(ask) for ask in open_asks if ask.get("id")]


def owner_words(action: dict, ask: dict) -> Optional[str]:
    """The owner's words for ask_owner.py answer: the picked option's own text, or what they typed."""
    options = ask.get("options") or []
    kind = action.get("kind")
    if kind == "text":
        return (action.get("text") or "").strip() or None
    picked = action.get("option")
    if kind == "accept":
        rec = ask.get("rec") or {}
        picked = rec.get("option")
    if picked and len(picked) == 1 and picked in string.ascii_uppercase:
        index = string.ascii_uppercase.index(picked)
        if index < len(options):
            return options[index]
    return None

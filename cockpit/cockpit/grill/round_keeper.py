from typing import Callable, List, Optional

from cockpit.asks.asks import Asks
from cockpit.grill.grill import Grill
from cockpit.grill.questions import ask_id_of, build_round, owner_words
from cockpit.source_unavailable import SourceUnavailable

TOPIC = "Your asks (cockpit)"
MAX_WORDS = 2000  # characters of the owner's own answer; panel.json keeps it whole


class RoundKeeper:
    """The agent side of the owner's grill round, done by code: an answer goes to ask_owner.py answer in the
    owner's words and the question is marked answered; nothing else is decided here (docs/GRILL.md)."""

    def __init__(self, grill: Grill, asks: Asks, doc_path: str, log: Callable[[str], None],
                 forward: Optional[Callable[[dict, str], str]] = None):
        self.grill = grill
        self.asks = asks
        self.doc_path = doc_path
        self.log = log
        self.session: Optional[str] = None
        self.url: Optional[str] = None
        self.handled = 0
        self.results: List[str] = []
        # Types a thread comment into the asking session's pane and says what happened (the owner, 2026-10-16: forward it).
        self.forward = forward or (lambda ask, text: "Not forwarded: the cockpit has no way to reach that session.")

    def start(self, ids: Optional[List[str]] = None) -> str:
        """A round of the asks the owner ticked (the owner, 2026-10-16), opened in its own tab, never embedded."""
        open_asks = [a for a in self.asks.read().open if ids is None or a.get("id") in ids]
        questions = build_round(open_asks)
        if not questions:
            raise SourceUnavailable("None of the asks you ticked is still open on the panel.")
        self.session = self.grill.create(TOPIC, "Answer the owner's open panel asks from the cockpit.", self.doc_path)
        self.grill.patch(self.session, {"questions": questions, "agent": {"status": "waiting", "handled": 0}})
        self.url = self.grill.serve(self.session)
        self.handled = 0
        return self.url

    def answer_one(self, ask_id: str, option: str, text: str) -> str:
        state = self.asks.read()
        ask = next((a for a in state.open if a.get("id") == ask_id), None)
        closed = next((a for a in state.answered if a.get("id") == ask_id), None) if ask is None else None
        if ask is None and closed is None:
            raise SourceUnavailable(f"Ask {ask_id} is not on the panel.")
        words = words_from_row(ask or closed, option, text)
        if not words:
            raise SourceUnavailable("Pick one of its options or write your own answer.")
        if closed is not None:
            # A row staged before the ask closed elsewhere (another window, a second click): the panel keeps its first
            # answer, and the owner's new words reach brain instead of being refused (the owner, 2026-10-28).
            self.log(f"ask {ask_id} was already answered ({closed.get('answer', '')!r}); the owner's new words for brain: {words!r}")
            self.results.append(f"Ask {ask_id} was already answered; the owner's new words: {words}")
            return words
        said = self.asks.answer(ask_id, words)
        self.log(f"answered ask {ask_id} in its row with the owner's words: {words!r} ({said})")
        self.results.append(f"Ask {ask_id} answered: {words}")
        return words

    def handle_sends(self) -> None:
        if not self.session:
            return
        for send in self.grill.sends_after(self.session, self.handled):
            self.handle(send)

    def handle(self, send: dict) -> None:
        by_id = {a.get("id"): a for a in self.asks.read().open}
        changes = []
        for action in send.get("actions") or []:
            question = action.get("q") or ""
            ask = by_id.get(ask_id_of(question) or "")
            kind = action.get("type")
            if kind == "answer" and ask:
                words = owner_words(action, ask)
                if words:
                    said = self.asks.answer(ask["id"], words)
                    self.log(f"answered ask {ask['id']} with the owner's words: {words!r} ({said})")
                    self.results.append(f"Ask {ask['id']} answered: {words}")
                    changes.append({"id": question, "status": "answered", "answer": answer_record(action), "updated": False})
            elif kind == "thread" and question:
                said = self.forward(ask or {}, action.get("text", "")) if ask else "Not forwarded: that ask is no longer open."
                changes.append({"id": question, "thread": [{"who": "user", "text": action.get("text", ""), "at": send.get("at")},
                                                           {"who": "agent", "text": said}]})
        patch = {"agent": {"status": "waiting", "handled": int(send.get("seq") or 0)}}
        if changes:
            patch["questions"] = changes
        self.grill.patch(self.session, patch)
        self.handled = int(send.get("seq") or self.handled)


def words_from_row(ask: dict, option: str, text: str) -> Optional[str]:
    """An answer given in its row: an option letter, or the owner's own words (never both, never empty)."""
    if text.strip():
        return text.strip()[:MAX_WORDS]
    return owner_words({"kind": "option", "option": option}, ask) if option else None


def answer_record(action: dict) -> dict:
    record = {"kind": action.get("kind")}
    for key in ("option", "options", "text"):
        if key in action:
            record[key] = action[key]
    return record

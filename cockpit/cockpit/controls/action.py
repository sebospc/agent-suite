from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Action:
    """One control the owner sent, with what the session looked like before it, so its effect is proved from the
    source afterwards and never from the cockpit's own claim."""
    id: str
    kind: str            # compact | clear | effort | prompt (a Needs you prompt)
    session: str
    text: str            # what was typed into the pane
    sent_at: float
    before_context: Optional[int]
    before_effort: str
    before_session_id: str
    level: str = field(default="")
    origin: str = field(default="owner")   # owner | autopilot
    reason: str = field(default="")        # the autopilot rule that sent it


def from_record(record: dict) -> Action:
    """An action back from its "sent" line in actions.jsonl."""
    return Action(id=record["id"], kind=record["kind"], session=record["session"], text=record.get("text", ""), sent_at=record["t"],
                  before_context=record.get("before_context"), before_effort=record.get("before_effort", ""),
                  before_session_id=record.get("before_session_id", ""), level=record.get("level", ""),
                  origin=record.get("origin", "owner"), reason=record.get("reason", ""))

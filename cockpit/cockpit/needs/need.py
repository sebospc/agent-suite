from dataclasses import dataclass, field


@dataclass(frozen=True)
class Need:
    """One row of Needs you: a level word, one sentence, its source, one action. In phase 1 an action
    copies a command (copy), types its prompt into the target session's pane on the owner's click (send; design chat
    N8, N11), jumps to a section (jump), sends a phase 2 control to the target session (control, payload is its kind),
    or waits (none)."""
    id: str
    level: str  # warning | caution
    text: str
    source: str
    action_label: str
    action_kind: str
    action_payload: str = field(default="")
    target: str = field(default="")  # the session whose pane the text goes into
